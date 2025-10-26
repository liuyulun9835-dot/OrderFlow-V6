using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;

namespace AtasCustomIndicators.V63
{
    // 类名改为带版本后缀，避免与旧类型冲突
    public class SimplifiedDataExporterV63 : ATAS.Indicators.Indicator
    {
        private const string SchemaVersion = "v6.3";
        private readonly object _syncRoot = new();
        private readonly Queue<(DateTimeOffset Timestamp, double Delta)> _rollingWindow = new();
        private readonly Dictionary<DateTimeOffset, ExportPayload> _pendingByMinute = new();
        private readonly string _logPath;

        private double _cumulativeDelta;
        private bool _jsonIndent;
        private string _exportDir;
        private SessionModeDefinition _sessionModeDefinition;
        private DateTimeOffset? _lastProcessedMinuteUtc;
        private DateTimeOffset? _sessionAnchorUtc;
        private JsonSerializerSettings? _serializerSettings;
        private bool _initialized;
        private bool _firstOnCalculateLogged;
        private bool _logDirectoryEnsured;
        private long _flushSequence;

        public SimplifiedDataExporterV63()
        {
            _logPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "ATAS",
                "Indicators",
                "exporter.log");

            Log("Constructor begin");

            // 指标显示名也改为新标识
            Name = "SimplifiedDataExporter_v63";

            _exportDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "ATAS",
                "Exports");

            SessionMode = "rolling:60";
            WriteOnBarCloseOnly = true;
            OutputTimezone = TimezoneOption.UTC;
            Backfill = false;
            JsonIndent = false;

            Log("Constructor end");
        }

        [DisplayName("SessionMode")]
        [Description("Session reset strategy: rolling:Nmin or session")]
        public string SessionMode
        {
            get => _sessionModeDefinition.OriginalValue;
            set
            {
                _sessionModeDefinition = SessionModeDefinition.Parse(value);
                ResetSession();
            }
        }

        [DisplayName("WriteOnBarCloseOnly")]
        [Description("Write only once per completed bar (default true)")]
        public bool WriteOnBarCloseOnly { get; set; }

        [DisplayName("OutputTimezone")]
        [Description("Timestamp output timezone (UTC or Local)")]
        public TimezoneOption OutputTimezone { get; set; }

        [DisplayName("Backfill")]
        [Description("Indicates historical playback/backfill mode")]
        public bool Backfill { get; set; }

        [DisplayName("JsonIndent")]
        [Description("Pretty-print JSON output for debugging")]
        public bool JsonIndent
        {
            get => _jsonIndent;
            set
            {
                _jsonIndent = value;
                if (_serializerSettings != null)
                {
                    _serializerSettings.Formatting = _jsonIndent ? Formatting.Indented : Formatting.None;
                }
            }
        }

        [DisplayName("ExportDir")]
        [Description("Directory for exported JSON artifacts")]
        public string ExportDir
        {
            get => _exportDir;
            set
            {
                if (string.IsNullOrWhiteSpace(value))
                {
                    return;
                }

                _exportDir = value;
            }
        }

        [DisplayName("SafeMode")]
        [Description("先以最小字段导出，排除初始化卡顿；确认无卡顿后再关闭")]
        public bool SafeMode { get; set; } = true;

        private string ExporterVersion =>
            Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "0.0.0";

        protected override void OnCalculate(int bar, decimal value)
        {
            var firstInvocation = false;
            if (!_firstOnCalculateLogged)
            {
                firstInvocation = true;
                _firstOnCalculateLogged = true;
                Log("OnCalculate first begin");
            }

            try
            {
                if (bar < 0)
                {
                    return;
                }

                if (!_initialized)
                {
                    try
                    {
                        LazyInit();
                    }
                    catch (Exception initEx)
                    {
                        Log($"LazyInit error: {initEx}");
                        return;
                    }
                }

                var isCompletedBar = Backfill || bar == CurrentBar - 1;

                if (SafeMode && !isCompletedBar)
                {
                    return;
                }

                if (WriteOnBarCloseOnly && !isCompletedBar)
                {
                    return;
                }

                var candle = GetCandle(bar);
                if (candle == null)
                {
                    return;
                }

                var timestampUtc = ResolveUtcTimestamp(candle.Time);
                var minuteUtc = FloorToMinute(timestampUtc);
                var outputTimestamp = FormatTimestamp(minuteUtc);

                double? poc = null;
                double? vah = null;
                double? val = null;
                double? cvd = null;
                var absorption = new AbsorptionResult(false, double.NaN, string.Empty);
                double? delta = null;

                // Always compute delta & CVD (needed even in SafeMode)
                try
                {
                    Log("Delta extraction begin");
                    delta = ExtractDelta(candle);
                    Log("Delta extraction end");

                    Log("CVD update begin");
                    cvd = UpdateCvd(minuteUtc, delta);
                    Log("CVD update end");
                }
                catch (Exception ex)
                {
                    Log($"Delta/CVD computation error: {ex.Message}");
                }

                // Only compute profile values and absorption when not in SafeMode
                if (!SafeMode)
                {
                    Log("Profile extraction begin");
                    poc = ExtractProfileValue(candle, "POC", "PointOfControl", "PriceOfControl");
                    vah = ExtractProfileValue(candle, "VAH", "ValueAreaHigh");
                    val = ExtractProfileValue(candle, "VAL", "ValueAreaLow");
                    Log("Profile extraction end");

                    Log("Absorption evaluation begin");
                    absorption = ExtractAbsorption(candle, delta, (double)candle.Volume);
                    Log("Absorption evaluation end");
                }

                // ---- 单bar体积峰值 (SDK Direct Access v6.3) ----
                double? barVpoPrice = null, barVpoVol = null, barVpoLoc = null; string? barVpoSide = null;
                if (!SafeMode)
                {
                    Log("[VPO] begin SDK direct access");
                    try
                    {
                        // 使用 ATAS SDK 官方属性直接访问 (IndicatorCandle.MaxVolumePriceInfo)
                        // (不再使用 GetProperty 反射)
                        var maxVolInfo = candle.MaxVolumePriceInfo;

                        if (maxVolInfo != null)
                        {
                            // 成功获取到 SDK 提供的最大量价阶信息
                            barVpoPrice = Convert.ToDouble(maxVolInfo.Price, CultureInfo.InvariantCulture);
                            barVpoVol = Convert.ToDouble(maxVolInfo.Volume, CultureInfo.InvariantCulture);

                            // (不再使用 GetProperty 反射)
                            var low = Convert.ToDouble(candle.Low, CultureInfo.InvariantCulture);
                            var high = Convert.ToDouble(candle.High, CultureInfo.InvariantCulture);

                            if (high > low)
                                barVpoLoc = Math.Max(0.0, Math.Min(1.0, (barVpoPrice.GetValueOrDefault() - low) / (high - low)));

                            var bid = Convert.ToDouble(maxVolInfo.Bid, CultureInfo.InvariantCulture);
                            var ask = Convert.ToDouble(maxVolInfo.Ask, CultureInfo.InvariantCulture);

                            if (!double.IsNaN(ask) && !double.IsNaN(bid))
                                barVpoSide = ask > bid ? "bull" : bid > ask ? "bear" : "neutral";

                            Log($"[VPO] SDK Hit: MaxVolInfo found. Price={barVpoPrice} Vol={barVpoVol} Side={barVpoSide}");
                        }
                        else
                        {
                            // 如果 SDK 返回 null (可能在某些 tick 精度或无成交的 bar 上)
                            Log("[VPO] SDK Miss: candle.MaxVolumePriceInfo was null.");
                        }
                    }
                    catch (Exception ex)
                    {
                        // 捕获 API 调用或类型转换的异常
                        Log($"[VPO] SDK access error: {ex.Message}");
                    }
                }

                // attach computed VPO values to pending payload via local variables below
                var payloadForVpo = new ExportPayload
                {
                    TimestampUtc = minuteUtc,
                    TimestampString = outputTimestamp,
                    Open = Convert.ToDouble(candle.Open, CultureInfo.InvariantCulture),
                    High = Convert.ToDouble(candle.High, CultureInfo.InvariantCulture),
                    Low = Convert.ToDouble(candle.Low, CultureInfo.InvariantCulture),
                    Close = Convert.ToDouble(candle.Close, CultureInfo.InvariantCulture),
                    Volume = Convert.ToDouble(candle.Volume, CultureInfo.InvariantCulture),
                    Poc = poc,
                    Vah = vah,
                    Val = val,
                    Cvd = cvd,
                    AbsorptionDetected = absorption.Detected,
                    AbsorptionStrength = absorption.Strength,
                    AbsorptionSide = absorption.Side,
                    BarVpoPrice = barVpoPrice,
                    BarVpoVol = barVpoVol,
                    BarVpoLoc = barVpoLoc,
                    BarVpoSide = barVpoSide
                };

                _pendingByMinute[minuteUtc] = payloadForVpo;

                var completed = CollectCompletedMinutes(minuteUtc);
                foreach (var ready in completed)
                {
                    if (!SafeMode)
                    {
                        Log($"Write payload begin {ready.TimestampUtc:o}");
                    }

                    WritePayload(ready);

                    if (!SafeMode)
                    {
                        Log($"Write payload end {ready.TimestampUtc:o}");
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"OnCalculate error: {ex}");
            }
            finally
            {
                if (firstInvocation)
                {
                    Log("OnCalculate first end");
                }
            }
        }

        private List<ExportPayload> CollectCompletedMinutes(DateTimeOffset currentMinuteUtc)
        {
            var minutesToFlush = _pendingByMinute.Keys
                .Where(minute => minute < currentMinuteUtc) // right-closed：只刷已封闭的上一分钟
                .OrderBy(minute => minute)
                .ToList();

            var ready = new List<ExportPayload>();
            foreach (var minute in minutesToFlush)
            {
                if (_pendingByMinute.TryGetValue(minute, out var payload))
                {
                    payload.FlushSequence = ++_flushSequence;
                    ready.Add(payload);
                    _pendingByMinute.Remove(minute);
                    _lastProcessedMinuteUtc = minute;
                }
            }

            return ready;
        }

        private void WritePayload(ExportPayload payload)
        {
            try
            {
                var dayDir = Path.Combine(_exportDir, $"date={payload.TimestampUtc:yyyy-MM-dd}");
                Directory.CreateDirectory(dayDir);

                var latestPath = Path.Combine(_exportDir, "latest.json"); // keep at root for monitoring
                var dayFile = Path.Combine(dayDir, $"bar_{payload.TimestampUtc:yyyyMMdd}.jsonl");

                static object? N(double? x)
                    => (x.HasValue && (double.IsNaN(x.Value) || double.IsInfinity(x.Value))) ? null : x;
                static object? Nf(double x)
                    => (double.IsNaN(x) || double.IsInfinity(x)) ? null : x;

                var timestampUtcIso = payload.TimestampUtc.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture);
                var tzLabel = OutputTimezone.ToString(); // "UTC" or "Local"

                var windowId = payload.TimestampUtc.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture);
                var document = new Dictionary<string, object?>
                {
                    ["timestamp"] = payload.TimestampString,
                    ["timestamp_utc"] = timestampUtcIso,
                    ["tz"] = tzLabel,
                    ["open"] = payload.Open,
                    ["high"] = payload.High,
                    ["low"] = payload.Low,
                    ["close"] = payload.Close,
                    ["volume"] = payload.Volume,
                    ["poc"] = N(payload.Poc),
                    ["vah"] = N(payload.Vah),
                    ["val"] = N(payload.Val),
                    ["cvd"] = N(payload.Cvd),
                    ["absorption_detected"] = payload.AbsorptionDetected,
                    ["absorption_strength"] = Nf(payload.AbsorptionStrength),
                    ["absorption_side"] = payload.AbsorptionSide ?? string.Empty,
                    ["bar_vpo_price"] = N(payload.BarVpoPrice),
                    ["bar_vpo_vol"]   = N(payload.BarVpoVol),
                    ["bar_vpo_loc"]   = N(payload.BarVpoLoc),
                    ["bar_vpo_side"]  = payload.BarVpoSide ?? string.Empty,
                    ["window_id"] = windowId,
                    ["flush_seq"] = payload.FlushSequence,
                    ["window_convention"] = "[minute_open, minute_close] right-closed",
                    ["fingerprint"] = "V6-PARTITIONED",
                    ["filename_pattern"] = "bar_YYYYMMDD.jsonl",
                    ["exporter_version"] = ExporterVersion,
                    ["schema_version"] = SchemaVersion,
                    ["backfill"] = Backfill,
                    ["cvd_mode"] = _sessionModeDefinition.OriginalValue
                };

                if (_serializerSettings == null)
                {
                    Log("Serializer settings unavailable during WritePayload");
                    return;
                }

                var json = JsonConvert.SerializeObject(document, _serializerSettings);

                lock (_syncRoot)
                {
                    File.WriteAllText(latestPath, json);
                    File.AppendAllText(dayFile, json + Environment.NewLine);
                }
            }
            catch (Exception ex)
            {
                Log($"WritePayload error: {ex}");
            }
        }


        private void LazyInit()
        {
            if (_initialized) return;

            Log("LazyInit begin");

            var asm = Assembly.GetExecutingAssembly();
            Log($"[FPRINT] Assembly.Location = {asm.Location}");
            Log($"[FPRINT] Assembly.FullName = {asm.FullName}");

            // 三元身份打点，便于确认加载的是哪个程序集版本
            try
            {
                Log($"[ID] Name={asm.GetName().Name}");
                Log($"[ID] Version={asm.GetName().Version}");
                Log($"[ID] Location={asm.Location}");
            }
            catch { /* no-op */ }

            EnsureExportDirectory();

            _serializerSettings = new JsonSerializerSettings
            {
                ContractResolver = new CamelCasePropertyNamesContractResolver(),
                // FloatFormatHandling = FloatFormatHandling.Symbol,
                DateFormatString = "o",
                Formatting = _jsonIndent ? Formatting.Indented : Formatting.None
            };

            _initialized = true;
            Log("LazyInit end");
        }


        private DateTimeOffset ResolveUtcTimestamp(DateTime candleTime)
        {
            if (candleTime.Kind == DateTimeKind.Utc)
            {
                return new DateTimeOffset(candleTime, TimeSpan.Zero);
            }

            var localTime = candleTime.Kind switch
            {
                DateTimeKind.Local => candleTime,
                DateTimeKind.Unspecified => DateTime.SpecifyKind(candleTime, DateTimeKind.Local),
                _ => candleTime.ToLocalTime()
            };

            return new DateTimeOffset(localTime.ToUniversalTime(), TimeSpan.Zero);
        }

        private string FormatTimestamp(DateTimeOffset minuteUtc)
        {
            var target = OutputTimezone == TimezoneOption.UTC
                ? minuteUtc.ToUniversalTime()
                : minuteUtc.ToLocalTime();

            return target.ToString("o", CultureInfo.InvariantCulture);
        }

        private static DateTimeOffset FloorToMinute(DateTimeOffset value)
        {
            return new DateTimeOffset(
                value.Year,
                value.Month,
                value.Day,
                value.Hour,
                value.Minute,
                0,
                TimeSpan.Zero);
        }

        private double? ExtractProfileValue(object candle, params string[] propertyNames)
        {
            try
            {
                foreach (var propertyName in propertyNames)
                {
                    var property = candle.GetType().GetProperty(propertyName);
                    if (property != null)
                    {
                        var result = property.GetValue(candle);
                        if (TryConvertToDouble(result, out var numeric))
                        {
                            return numeric;
                        }
                    }
                }

                var profileProperty = candle.GetType().GetProperty("Profile");
                if (profileProperty != null)
                {
                    var profile = profileProperty.GetValue(candle);
                    if (profile != null)
                    {
                        foreach (var propertyName in propertyNames)
                        {
                            var property = profile.GetType().GetProperty(propertyName);
                            if (property != null)
                            {
                                var result = property.GetValue(profile);
                                if (TryConvertToDouble(result, out var numeric))
                                {
                                    return numeric;
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"ExtractProfileValue error: {ex.Message}");
            }

            return double.NaN;
        }

        private static bool TryConvertToDouble(object? input, out double result)
        {
            switch (input)
            {
                case null:
                    result = double.NaN;
                    return false;
                case double d when !double.IsNaN(d):
                    result = d;
                    return true;
                case float f when !float.IsNaN(f):
                    result = f;
                    return true;
                case decimal dec:
                    result = Convert.ToDouble(dec, CultureInfo.InvariantCulture);
                    return true;
                case IConvertible convertible:
                    try
                    {
                        result = convertible.ToDouble(CultureInfo.InvariantCulture);
                        return true;
                    }
                    catch
                    {
                        result = double.NaN;
                        return false;
                    }
                default:
                    if (double.TryParse(Convert.ToString(input, CultureInfo.InvariantCulture), NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed))
                    {
                        result = parsed;
                        return true;
                    }
                    result = double.NaN;
                    return false;
            }
        }

        private double? ExtractDelta(object candle)
        {
            try
            {
                var deltaProperties = new[] { "Delta", "CumulativeDelta", "DeltaVolume" };
                foreach (var name in deltaProperties)
                {
                    var property = candle.GetType().GetProperty(name);
                    if (property != null)
                    {
                        var raw = property.GetValue(candle);
                        if (TryConvertToDouble(raw, out var value))
                        {
                            return value;
                        }
                    }
                }

                var buyVolume = ExtractVolumeSide(candle, "BuyVolume", "AskVolume", "UpVolume");
                var sellVolume = ExtractVolumeSide(candle, "SellVolume", "BidVolume", "DownVolume");

                if (buyVolume.HasValue && sellVolume.HasValue)
                {
                    return buyVolume.Value - sellVolume.Value;
                }
            }
            catch (Exception ex)
            {
                Log($"ExtractDelta error: {ex.Message}");
            }

            return null;
        }

        private double? ExtractVolumeSide(object candle, params string[] propertyNames)
        {
            foreach (var name in propertyNames)
            {
                var property = candle.GetType().GetProperty(name);
                if (property != null)
                {
                    var value = property.GetValue(candle);
                    if (TryConvertToDouble(value, out var numeric))
                    {
                        return numeric;
                    }
                }
            }

            return null;
        }

        private double UpdateCvd(DateTimeOffset minuteUtc, double? delta)
        {
            if (_sessionModeDefinition.Mode == SessionModeKind.Session)
            {
                if (_sessionAnchorUtc == null || (_lastProcessedMinuteUtc.HasValue && minuteUtc < _lastProcessedMinuteUtc.Value))
                {
                    _cumulativeDelta = 0.0;
                    _sessionAnchorUtc = minuteUtc;
                }

                if (delta.HasValue)
                {
                    _cumulativeDelta += delta.Value;
                    return _cumulativeDelta;
                }

                return double.NaN;
            }

            if (_sessionModeDefinition.Mode == SessionModeKind.Rolling)
            {
                if (delta.HasValue)
                {
                    _rollingWindow.Enqueue((minuteUtc, delta.Value));
                    _cumulativeDelta += delta.Value;
                }

                var boundary = minuteUtc - _sessionModeDefinition.RollingWindow;
                while (_rollingWindow.Count > 0 && _rollingWindow.Peek().Timestamp < boundary)
                {
                    var item = _rollingWindow.Dequeue();
                    _cumulativeDelta -= item.Delta;
                }

                return delta.HasValue ? _cumulativeDelta : double.NaN;
            }

            return double.NaN;
        }

        private AbsorptionResult ExtractAbsorption(object candle, double? delta, double totalVolume)
        {
            try
            {
                var absorptionProperty = candle.GetType().GetProperty("Absorption");
                if (absorptionProperty != null)
                {
                    var absorption = absorptionProperty.GetValue(candle);
                    if (absorption != null)
                    {
                        var detected = ExtractBoolean(absorption, "Detected", "IsAbsorption", "Triggered");
                        var strength = ExtractNumeric(absorption, "Strength", "Score", "Volume");
                        var side = ExtractString(absorption, "Side", "Direction", "Type");

                        return new AbsorptionResult(
                            detected ?? false,
                            strength ?? double.NaN,
                            side ?? string.Empty);
                    }
                }

                if (totalVolume <= double.Epsilon)
                {
                    return new AbsorptionResult(false, double.NaN, string.Empty);
                }

                if (delta.HasValue)
                {
                    var imbalance = 1.0 - Math.Min(1.0, Math.Abs(delta.Value) / Math.Max(totalVolume, 1e-9));
                    var detected = imbalance > 0.6 && totalVolume > 0.0;
                    var side = delta.Value > 0 ? "buy" : delta.Value < 0 ? "sell" : string.Empty;
                    var strength = detected ? imbalance : double.NaN;
                    return new AbsorptionResult(detected, strength, side);
                }
            }
            catch (Exception ex)
            {
                Log($"ExtractAbsorption error: {ex.Message}");
            }

            return new AbsorptionResult(false, double.NaN, string.Empty);
        }

        private static bool? ExtractBoolean(object source, params string[] propertyNames)
        {
            foreach (var name in propertyNames)
            {
                var property = source.GetType().GetProperty(name);
                if (property != null)
                {
                    var value = property.GetValue(source);
                    if (value is bool boolean)
                    {
                        return boolean;
                    }

                    if (value is IConvertible convertible)
                    {
                        try
                        {
                            return convertible.ToBoolean(CultureInfo.InvariantCulture);
                        }
                        catch
                        {
                        }
                    }
                }
            }

            return null;
        }

        private static double? ExtractNumeric(object source, params string[] propertyNames)
        {
            foreach (var name in propertyNames)
            {
                var property = source.GetType().GetProperty(name);
                if (property != null)
                {
                    var value = property.GetValue(source);
                    if (TryConvertToDouble(value, out var numeric))
                    {
                        return numeric;
                    }
                }
            }

            return null;
        }

        private static string? ExtractString(object source, params string[] propertyNames)
        {
            foreach (var name in propertyNames)
            {
                var property = source.GetType().GetProperty(name);
                if (property != null)
                {
                    var value = property.GetValue(source);
                    if (value != null)
                    {
                        return Convert.ToString(value, CultureInfo.InvariantCulture);
                    }
                }
            }

            return null;
        }

        private void ResetSession()
        {
            _cumulativeDelta = 0.0;
            _rollingWindow.Clear();
            _pendingByMinute.Clear();
            _sessionAnchorUtc = null;
            _lastProcessedMinuteUtc = null;
            _flushSequence = 0;
        }

        private void EnsureExportDirectory()
        {
            if (string.IsNullOrWhiteSpace(_exportDir))
            {
                throw new InvalidOperationException("Export directory path is not configured.");
            }

            try
            {
                Directory.CreateDirectory(_exportDir);

                try
                {
                    var dirLower = _exportDir.Replace('\\', '/').ToLowerInvariant();
                    if (dirLower.Contains("/date=") || dirLower.EndsWith("date="))
                        Log($"[WARN] ExportDir appears to contain a 'date=' partition: '{_exportDir}'. " +
                            "WritePayload will append its own 'date=YYYY-MM-DD' child — ensure ExportDir points to the partition ROOT, e.g. ...\\resolution=1m");
                }
                catch { /* no-op */ }
            }
            catch (Exception ex)
            {
                Log($"EnsureExportDirectory error: {ex.Message}");
                throw;
            }
        }

        private void Log(string message)
        {
            try
            {
                if (!_logDirectoryEnsured)
                {
                    var directory = Path.GetDirectoryName(_logPath);
                    if (!string.IsNullOrWhiteSpace(directory))
                    {
                        Directory.CreateDirectory(directory);
                    }

                    _logDirectoryEnsured = true;
                }

                File.AppendAllText(_logPath, $"{DateTime.UtcNow:o} {message}{Environment.NewLine}");
            }
            catch
            {
                // suppress logging failures
            }
        }

    }

    // 这些类型放回同一命名空间：AtasCustomIndicators.V63
    public enum TimezoneOption
    {
        UTC,
        Local
    }

    internal enum SessionModeKind
    {
        Rolling,
        Session
    }

    internal readonly struct SessionModeDefinition
    {
        public SessionModeDefinition(SessionModeKind mode, TimeSpan rollingWindow, string original)
        {
            Mode = mode;
            RollingWindow = rollingWindow;
            OriginalValue = original;
        }

        public SessionModeKind Mode { get; }
        public TimeSpan RollingWindow { get; }
        public string OriginalValue { get; }

        public static SessionModeDefinition Parse(string? raw)
        {
            if (string.IsNullOrWhiteSpace(raw))
            {
                return new SessionModeDefinition(SessionModeKind.Rolling, TimeSpan.FromMinutes(60), "rolling:60");
            }

            var text = raw!.Trim();
            if (text.StartsWith("rolling", StringComparison.OrdinalIgnoreCase))
            {
                var parts = text.Split(':');
                if (parts.Length == 2 && int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var minutes) && minutes > 0)
                {
                    return new SessionModeDefinition(SessionModeKind.Rolling, TimeSpan.FromMinutes(minutes), text);
                }

                return new SessionModeDefinition(SessionModeKind.Rolling, TimeSpan.FromMinutes(60), text);
            }

            if (string.Equals(text, "session", StringComparison.OrdinalIgnoreCase))
            {
                return new SessionModeDefinition(SessionModeKind.Session, TimeSpan.Zero, text);
            }

            return new SessionModeDefinition(SessionModeKind.Rolling, TimeSpan.FromMinutes(60), text);
        }
    }

    internal sealed class ExportPayload
    {
        public DateTimeOffset TimestampUtc { get; set; }
        public string TimestampString { get; set; } = string.Empty;
        public double Open { get; set; }
        public double High { get; set; }
        public double Low { get; set; }
        public double Close { get; set; }
        public double Volume { get; set; }
        public double? Poc { get; set; }
        public double? Vah { get; set; }
        public double? Val { get; set; }
        public double? Cvd { get; set; }
        public bool AbsorptionDetected { get; set; }
        public double AbsorptionStrength { get; set; }
        public string? AbsorptionSide { get; set; }
        public long FlushSequence { get; set; }

        // 新增字段：Bar VPO 信息
        public double? BarVpoPrice { get; set; }
        public double? BarVpoVol { get; set; }
        public double? BarVpoLoc { get; set; }
        public string? BarVpoSide { get; set; }
    }

    internal readonly struct AbsorptionResult
    {
        public AbsorptionResult(bool detected, double strength, string side)
        {
            Detected = detected;
            Strength = strength;
            Side = side;
        }

        public bool Detected { get; }
        public double Strength { get; }
        public string Side { get; }
    }
} // 结束 namespace AtasCustomIndicators.V63
