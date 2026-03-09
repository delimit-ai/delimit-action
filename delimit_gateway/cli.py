#!/usr/bin/env python3
"""
Delimit Gateway CLI
Provides command-line interface to V12 governance engine
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.surface_bridge import SurfaceBridge


def main():
    parser = argparse.ArgumentParser(description='Delimit Governance Gateway')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # validate-api command
    validate_parser = subparsers.add_parser('validate-api', help='Check API for breaking changes')
    validate_parser.add_argument('old_spec', help='Path to old API specification')
    validate_parser.add_argument('new_spec', help='Path to new API specification')
    validate_parser.add_argument('--version', help='Task version', default=None)
    validate_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # check-policy command
    policy_parser = subparsers.add_parser('check-policy', help='Check API against policy rules')
    policy_parser.add_argument('spec_files', nargs='+', help='API specification files')
    policy_parser.add_argument('--policy-file', help='Path to policy file')
    policy_parser.add_argument('--version', help='Task version', default=None)
    policy_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # explain-diff command
    diff_parser = subparsers.add_parser('explain-diff', help='Explain differences between API specs')
    diff_parser.add_argument('old_spec', help='Path to old API specification')
    diff_parser.add_argument('new_spec', help='Path to new API specification')
    diff_parser.add_argument('--detail', choices=['summary', 'medium', 'detailed'], default='medium')
    diff_parser.add_argument('--version', help='Task version', default=None)
    diff_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    bridge = SurfaceBridge()
    
    try:
        if args.command == 'validate-api':
            evidence = bridge.validate_api(args.old_spec, args.new_spec, args.version)
        elif args.command == 'check-policy':
            evidence = bridge.check_policy(
                args.spec_files,
                policy_file=args.policy_file,
                version=args.version
            )
        elif args.command == 'explain-diff':
            evidence = bridge.explain_diff(
                args.old_spec,
                args.new_spec,
                detail_level=args.detail,
                version=args.version
            )
        else:
            print(f"Unknown command: {args.command}")
            return 1
        
        # Output results
        if args.json:
            print(json.dumps(evidence, indent=2))
        else:
            print(bridge.format_for_cli(evidence))
        
        return evidence.get('exit_code', 0)
        
    except Exception as e:
        if args.json:
            error = {
                "task": args.command,
                "decision": "fail",
                "exit_code": 1,
                "summary": f"Task execution failed: {str(e)}"
            }
            print(json.dumps(error, indent=2))
        else:
            print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())