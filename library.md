# Project Dependencies

| Library | Version | Purpose | Referenced In |
| --- | --- | --- | --- |
| **FreeCAD** | Latest | Loads STEP files, tessellates meshes, and provides shape primitives for projection. | `server/cad_service.py`, `server/freecad_setup.py` |
| **pythonocc-core** | Latest | OpenCascade Python bindings for hidden-line removal (HLR), edge discretization, and mid-plane sectioning. | `server/cad_service_occ.py` |
| **FastAPI** | 0.111.0 | Exposes REST endpoints for uploads, view generation, streaming, and ZIP exports. | `server/main.py` |
| **uvicorn** | 0.30.1 | ASGI server for local development and production deployments. | `server/main.py` (launcher) |
| **python-multipart** | 0.0.9 | Enables FastAPI to parse multipart/form-data uploads. | `server/main.py` (FastAPI dependency) |
| **pydantic** | 2.7.1 | FastAPI request/response validation framework. | Transitive through `fastapi` |
| **aiofiles** | 23.2.1 | Async file I/O for efficient streaming. | Ready for use in `server/main.py` |
| **numpy** | 1.26.4 | Vectorized tessellation data handling and projection math. | `server/cad_service.py`, `server/cad_service_occ.py` |
| **matplotlib** | 3.9.0 | Renders projected wireframes and silhouettes into blueprint-style PNGs. | `server/cad_service.py`, `server/cad_service_occ.py` |
| **trimesh** | 4.5.0 | Converts FreeCAD tessellation to glTF/GLB without GUI dependencies. | `server/cad_service.py` |
| **pytest** | Latest | Testing framework for dependency verification. | `tests/test_dependencies.py` |
