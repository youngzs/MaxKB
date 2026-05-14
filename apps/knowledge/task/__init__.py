# Ensure the async OCR celery task gets registered with the worker.
# Unlike embedding/generate/sync (which are imported at module level by the
# serializers), ocr.py is only referenced via lazy imports, so without this
# the worker would never load it and `celery:ocr_pdf_document` would be
# unregistered. ocr.py keeps its module-level imports to stdlib + celery_app
# only, so importing it here is circular-import-safe.
from . import ocr  # noqa: F401
