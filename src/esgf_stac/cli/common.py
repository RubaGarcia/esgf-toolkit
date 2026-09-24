"""Shared argparse options for all esgf-stac CLIs."""

from esgf_stac import NODES


def add_node_arg(ap, default="east"):
    ap.add_argument("--node", choices=NODES, default=default, help="ESGF STAC node (default: east)")


def add_filter_args(ap, include_rcm=True):
    ap.add_argument("--collection", help="Filter by collection (e.g. CMIP7); omit to search all")
    ap.add_argument("--model", help="Model / source_id, comma-separated")
    if include_rcm:
        ap.add_argument("--rcm-model", dest="rcm_model", help="RCM / source_id, comma-separated")
        ap.add_argument("--driving-model", dest="driving_model", help="Driving model / driving_source_id")
    ap.add_argument("--experiment", help="Experiment / scenario, comma-separated")
    ap.add_argument("--variable", help="Variable_id, comma-separated (e.g. tas,hurs)")
    ap.add_argument("--frequency", help="Frequency, comma-separated (e.g. mon,day)")
    ap.add_argument("--grid", help="Grid label, comma-separated (e.g. gr,native)")
    ap.add_argument("--member", help="Variant/member label, comma-separated")
    ap.add_argument("--domain", help="Realm, comma-separated (e.g. atmos,ocean)")
    ap.add_argument("--activity", help="Activity_id, comma-separated")


def build_filters(args, include_rcm=True) -> dict:
    """Collect CLI filter arguments into the {column: value} dict for build_body."""
    filters = {
        "model": args.model,
        "experiment": args.experiment,
        "variable": args.variable,
        "frequency": args.frequency,
        "grid": args.grid,
        "member": args.member,
        "domain": args.domain,
        "activity": getattr(args, "activity", None),
    }
    if include_rcm:
        filters["rcm_model"] = getattr(args, "rcm_model", None)
        filters["driving_model"] = getattr(args, "driving_model", None)
    return filters


def add_health_arg(ap):
    ap.add_argument("--health", default="./health.csv", help="Health CSV (default: ./health.csv)")
