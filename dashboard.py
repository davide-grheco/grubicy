from signac_dashboard import Dashboard
from signac_dashboard.modules import (DocumentList, FileList, ImageViewer,
                                      Notes, Schema, StatepointList,
                                      TextDisplay)

from dashboard_modules.param_set_viewer import ParamSetViewer

modules = [
    # Per-job cards
    StatepointList(context="JobContext"),
    DocumentList(context="JobContext"),
    FileList(context="JobContext"),
    # If you generate plots per job, e.g. workspace/<id>/analysis/*.png
    # ImageViewer(context="JobContext", glob="analysis/*.png"),
    # Collaboration / QC
    Notes(context="JobContext", key="notes"),
    ParamSetViewer(),
    # Project-level cards
    Schema(context="ProjectContext"),
    DocumentList(context="ProjectContext"),
    TextDisplay(
        context="ProjectContext",
        name="Project Summary",
        #        text="### GBSA study dashboard\nUse the search bar with `sp.` and `doc.` filters.",
    ),
]

if __name__ == "__main__":
    Dashboard(modules=modules).main()
