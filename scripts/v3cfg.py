"""Shared V3 settings. Resolution via env V3_RES (10 default; 20 reproduces the first 20 m run)."""
import os

V3 = os.environ.get("V3_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")
# V2 derived rasters (optical_v2 release) are inputs to s01 only; set V2_DATA if they live elsewhere
V2_DATA = os.environ.get("V2_DATA") or f"{V3}/../V2/Esk_MVP_Optical_v2_2026-09-23"
AOI = f"{V3}/aoi/esk_catchment.geojson"          # HBRC Esk catchment boundary
NZ_LOCATOR = f"{V3}/aoi/nz_locator.geojson"
# Earth Engine Cloud project: env EE_PROJECT, or one line in the untracked file ee_project.txt
_ee = f"{V3}/ee_project.txt"
EE_PROJECT = os.environ.get("EE_PROJECT") or (open(_ee).read().strip() if os.path.exists(_ee) else None)
RES = int(os.environ.get("V3_RES", 10))
SUF = "" if RES == 20 else f"_{RES}m"
PX_HA = RES * RES / 1e4
MMU_PX = {20: 2, 10: 4}[RES]          # 0.08 ha at 20 m, 0.04 ha at 10 m
STREAM_HA = 5.0                        # contributing area defining a stream
STACK = f"{V3}/data/esk_v3_stack{SUF}.nc"
SAMPLE = os.environ.get("V3_SAMPLE") or (f"{V3}/sample" if RES == 10 else f"{V3}/sample_20m_superseded")
