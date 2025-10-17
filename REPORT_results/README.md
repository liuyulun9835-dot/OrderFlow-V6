# Results Reproducibility Guide
Each experiment must record:
- git commit hash
- git tag (semantic versioning, e.g., v6.0.0-alpha1)
- random seed (see utils/seed.py)
- model path in ../models
Re-run experiments by checking out the tag and executing:


## Windows 一键运行（无 make）
```powershell
.\scripts\make_data_pipeline.ps1 -AtasDir "$env:USERPROFILE\Documents\ATAS\Exports" -Symbol "BTC/USDT" -Since "2020-01-01" -Until "2025-10-12"
```
