from __future__ import annotations
import argparse, subprocess, sys
from ..config import ToolConfig
from ..core.session import load_session
from ..core import routing, motion
from ..backends.registry import build_registry
from ..sdr.hackrf import HackRfTransmitter
from ..sdr.limesdr import LimeSdrTransmitter
from .. import pipeline

def _transmitter(cfg, device):
    if device == "LimeSDR":
        return LimeSdrTransmitter(cfg.resolve_tool("soapy"))
    return HackRfTransmitter(cfg.resolve_tool("hackrf"))

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ghostsignal-cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("session")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--generate-only", action="store_true")
    run.add_argument("--nav", default="brdc.nav")
    run.add_argument("--work-dir", default=".")
    args = ap.parse_args(argv)

    cfg = ToolConfig()
    s = load_session(args.session)
    route = routing.build_route(s.waypoints, s.transport)
    traj = motion.build_trajectory(route, s.speed_profile)
    registry = build_registry(cfg)
    gen = registry[s.sdr.constellation]
    tx = _transmitter(cfg, s.sdr.device)
    start_time = s.start_time_utc.replace("-", "/").replace("T", ",").replace("Z", "")
    plan = pipeline.plan_pipeline(generator=gen, transmitter=tx, sdr=s.sdr,
                                  trajectory=traj, nav_file=args.nav,
                                  start_time=start_time, work_dir=args.work_dir)
    if args.dry_run:
        print(" ".join(plan.gen_argv))
        print(" ".join(plan.tx_argv))
        return 0
    def writer(p, t): open(p, "w", encoding="utf-8").write(t)
    def runner(a):
        if args.generate_only and a == plan.tx_argv:
            return 0
        return subprocess.run(a).returncode
    return pipeline.run_pipeline(plan, writer=writer, runner=runner,
                                 on_event=lambda stage, d: print(f"[{stage}]", d))

if __name__ == "__main__":
    sys.exit(main())
