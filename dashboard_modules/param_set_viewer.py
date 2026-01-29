import json
from pathlib import Path

from flask import render_template_string
from markupsafe import escape
from signac_dashboard.module import Module


class ParamSetViewer(Module):
    _supported_contexts = {"JobContext"}

    def __init__(
        self,
        name="Resolved Parameters",
        context="JobContext",
        param_subdir="configs/param-sets",
        **kwargs,
    ):
        # template is required by Module, but we render via render_template_string
        super().__init__(
            name=name, context=context, template="cards/blank.html", **kwargs
        )
        self.param_subdir = Path(param_subdir)

    def _project_root(self, job):
        # robust across signac versions
        try:
            return Path(job.project.root_directory())
        except Exception:
            return Path(job._project.root_directory())

    def get_cards(self, job):
        ps_id = job.sp.get("param_set_id")
        if not ps_id:
            text = "No param_set_id in state point."
        else:
            root = self._project_root(job)
            path = root / self.param_subdir / f"{ps_id}.json"
            if not path.exists():
                text = f"Missing param set file: {path}"
            else:
                params = json.loads(path.read_text())
                text = json.dumps(params, indent=2, sort_keys=True)

        html = render_template_string(
            "<pre style='white-space: pre-wrap;'>{{ txt }}</pre>",
            txt=escape(text),
        )
        return [{"name": self.name, "content": html}]
