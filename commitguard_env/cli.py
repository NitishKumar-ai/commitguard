import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from .scanner import CommitGuardScanner


def cmd_scan(args):
    diff_text = ""
    if getattr(args, "diff", None):
        diff_text = Path(args.diff).read_text(encoding="utf-8")
    elif getattr(args, "staged", False):
        diff_text = subprocess.check_output(["git", "diff", "--staged"], text=True)
    elif getattr(args, "commit", None):
        diff_text = subprocess.check_output(["git", "show", args.commit], text=True)
    elif getattr(args, "pr", None):
        diff_text = subprocess.check_output(["gh", "pr", "diff", args.pr], text=True)
    else:
        print("Must specify one of --diff, --staged, --commit, or --pr")
        sys.exit(1)

    if not diff_text.strip():
        print("No diff found to scan.")
        sys.exit(0)

    print(f"Loading model ({args.model})...", file=sys.stderr)
    scanner = CommitGuardScanner(model_path=args.model, is_lora=args.is_lora, base_model=args.base_model)
    
    print(f"Scanning diff ({len(diff_text)} chars)...", file=sys.stderr)
    result = scanner.scan(diff_text)
    
    if args.format == "json":
        print(json.dumps(asdict(result), indent=2))
    elif args.format == "text":
        status = "VULNERABLE ⚠️" if result.is_vulnerable else "SAFE ✅"
        print(f"\nVerdict: {status}")
        if result.is_vulnerable:
            print(f"CWE: {result.cwe}")
            print(f"Exploit Sketch:\n  {result.exploit_sketch}")
        if result.parse_error:
            print(f"\nParser Warning: {result.parse_error}")
    elif args.format == "sarif":
        # Minimal SARIF output stub
        print("SARIF format not fully implemented yet.", file=sys.stderr)
        print(json.dumps(asdict(result)))
        
    if args.fail_on_vulnerable and result.is_vulnerable:
        sys.exit(1)


def cmd_server(args):
    from .server import main as server_main
    server_main()


def cmd_eval(args):
    # This is a bit hacky to reuse the script without modifying sys.path everywhere
    # A cleaner approach would be moving evaluate.py into commitguard_env
    REPO_ROOT = Path(__file__).resolve().parent.parent
    eval_script = REPO_ROOT / "scripts" / "evaluate.py"
    
    cmd = [sys.executable, str(eval_script)]
    cmd.extend(args.eval_args)
    subprocess.run(cmd, check=True)


def cmd_hook(args):
    from .hooks import install_hook
    
    if args.action == "install":
        if args.pre_commit:
            install_hook("pre-commit")
        elif args.pre_push:
            install_hook("pre-push")
        else:
            print("Please specify a hook type to install (e.g., --pre-commit or --pre-push)")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="CommitGuard AI-paced security review")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'scan' subcommand
    scan_parser = subparsers.add_parser("scan", help="Scan a code diff for vulnerabilities")
    
    source_group = scan_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--diff", type=str, help="Path to a diff file")
    source_group.add_argument("--staged", action="store_true", help="Scan git staged changes")
    source_group.add_argument("--commit", type=str, help="Scan a specific git commit (e.g., HEAD)")
    source_group.add_argument("--pr", type=str, help="Scan a GitHub PR URL or ID (requires gh cli)")
    
    scan_parser.add_argument("--model", type=str, default="inmodel-labs/commitguard-llama-3b", help="Model path or HF ID")
    scan_parser.add_argument("--base-model", type=str, default=None, help="Base model if using LoRA")
    scan_parser.add_argument("--is-lora", action="store_true", help="Whether the model is a LoRA adapter")
    scan_parser.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format")
    scan_parser.add_argument("--fail-on-vulnerable", action="store_true", help="Exit with code 1 if vulnerable")
    
    # 'server' subcommand
    server_parser = subparsers.add_parser("server", help="Start the OpenEnv environment server")
    # server_main takes PORT from environment
    
    # 'eval' subcommand
    eval_parser = subparsers.add_parser("eval", help="Run the evaluation harness")
    eval_parser.add_argument("eval_args", nargs=argparse.REMAINDER, help="Arguments passed to evaluate.py")

    # 'hook' subcommand
    hook_parser = subparsers.add_parser("hook", help="Manage git hooks")
    hook_parser.add_argument("action", choices=["install"], help="Action to perform (e.g., install)")
    hook_parser.add_argument("--pre-commit", action="store_true", help="Install pre-commit hook")
    hook_parser.add_argument("--pre-push", action="store_true", help="Install pre-push hook")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "server":
        cmd_server(args)
    elif args.command == "eval":
        cmd_eval(args)
    elif args.command == "hook":
        cmd_hook(args)

if __name__ == "__main__":
    main()
