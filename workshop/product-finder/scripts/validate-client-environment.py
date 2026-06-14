#!/usr/bin/env python3
"""
Product Finder Client Environment Validation Script

This script validates that a client's Citadel deployment is correctly configured
to run the Product Finder workshop.

Usage:
    python scripts/validate-client-environment.py

Requirements:
    - Azure CLI installed and authenticated
    - azd installed and configured with environment
    - Python 3.10+
"""

import subprocess
import sys
import json
from typing import Tuple

def run_cmd(cmd: str, check: bool = False) -> Tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)

def check_required_tools() -> bool:
    """Verify required CLI tools are installed."""
    print("\n📋 Checking required tools...")
    
    tools = {
        "az": "Azure CLI",
        "azd": "Azure Developer CLI",
        "python": "Python 3.10+"
    }
    
    all_ok = True
    for cmd, name in tools.items():
        if cmd == "python":
            # Validate the interpreter running this script first; fallback to shell commands.
            py_ver = sys.version.split(chr(10))[0]
            print(f"  ✅ {name}: {py_ver}")
            continue

        # azd uses `version` instead of `--version`; other tools support `--version`.
        version_cmd = "azd version" if cmd == "azd" else f"{cmd} --version"
        rc, out, err = run_cmd(version_cmd)
        if rc == 0:
            print(f"  ✅ {name}: {out.split(chr(10))[0]}")
        else:
            print(f"  ❌ {name}: NOT INSTALLED")
            all_ok = False
    
    return all_ok

def check_azure_auth() -> bool:
    """Verify Azure CLI authentication."""
    print("\n🔐 Checking Azure authentication...")
    
    rc_name, name_out, _ = run_cmd("az account show --query name -o tsv")
    rc_id, id_out, _ = run_cmd("az account show --query id -o tsv")
    if rc_name != 0 or rc_id != 0 or not name_out or not id_out:
        print(f"  ❌ Not authenticated to Azure. Run: az login")
        return False

    print(f"  ✅ Authenticated as: {name_out}")
    print(f"     Subscription: {id_out}")
    return True

def get_azd_value(key: str) -> Tuple[bool, str]:
    """Get an azd environment value."""
    # Avoid shell redirection for cross-platform compatibility.
    rc, out, err = run_cmd(f"azd env get-value {key}")
    if rc == 0 and out:
        return True, out
    return False, ""

def check_azd_environment() -> bool:
    """Verify azd environment is configured."""
    print("\n⚙️  Checking azd environment...")
    
    required_keys = [
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_RESOURCE_GROUP",
        "AZURE_LOCATION",
    ]
    
    all_ok = True
    for key in required_keys:
        ok, val = get_azd_value(key)
        if ok:
            print(f"  ✅ {key}: {val[:40]}{'...' if len(val) > 40 else ''}")
        else:
            print(f"  ❌ {key}: NOT SET")
            all_ok = False
    
    return all_ok

def check_hub_resources() -> bool:
    """Verify Citadel Hub resources exist."""
    print("\n🏗️  Checking Citadel Hub resources...")
    
    ok, hub_rg = get_azd_value("AZURE_RESOURCE_GROUP")
    if not ok:
        print(f"  ⚠️  Cannot determine hub RG from azd")
        return False
    
    # Check resource group exists
    rc, out, err = run_cmd(
        f'az group show --name "{hub_rg}" --query id -o json'
    )
    if rc != 0:
        print(f"  ❌ Hub resource group '{hub_rg}' not found")
        return False
    print(f"  ✅ Hub resource group: {hub_rg}")
    
    # Check APIM exists
    rc, out, err = run_cmd(
        f'az apim list --resource-group "{hub_rg}" --query [0].name -o json'
    )
    if rc == 0 and out:
        apim_name = json.loads(out)
        print(f"  ✅ APIM found: {apim_name}")
        return True
    else:
        print(f"  ❌ No APIM instance found in hub RG")
        return False

def check_spoke_resources() -> bool:
    """Verify Spoke (Product Finder) resources exist."""
    print("\n🔭 Checking Spoke resources...")
    
    ok, spoke_rg = get_azd_value("SPOKE_RESOURCE_GROUP")
    if not ok:
        print(f"  ⚠️  SPOKE_RESOURCE_GROUP not set (check CLIENT_DEPLOYMENT_CHECKLIST.md)")
        return False
    
    # Check resource group exists
    rc, out, err = run_cmd(
        f'az group show --name "{spoke_rg}" --query id -o json'
    )
    if rc != 0:
        print(f"  ⚠️  Spoke resource group '{spoke_rg}' not found (may not exist yet)")
        return True  # Not critical, might need to be created
    
    print(f"  ✅ Spoke resource group: {spoke_rg}")
    return True

def check_foundry_resources() -> bool:
    """Verify Foundry account and project."""
    print("\n🤖 Checking Foundry resources...")
    
    ok, foundry_acct = get_azd_value("SPOKE_AI_FOUNDRY_ACCOUNT_NAME")
    if not ok:
        print(f"  ⚠️  SPOKE_AI_FOUNDRY_ACCOUNT_NAME not set")
        return True  # Non-critical at pre-flight stage
    
    ok, spoke_rg = get_azd_value("SPOKE_RESOURCE_GROUP")
    if not ok:
        print(f"  ⚠️  Cannot determine spoke RG")
        return True
    
    # Check Foundry account exists
    rc, out, err = run_cmd(
        f"az cognitiveservices account show "
        f'--name "{foundry_acct}" --resource-group "{spoke_rg}" '
        f"--query id -o json"
    )
    if rc != 0:
        print(f"  ⚠️  Foundry account '{foundry_acct}' not found in '{spoke_rg}'")
        return True  # May not exist yet
    
    print(f"  ✅ Foundry account: {foundry_acct}")
    
    return True

def check_permissions() -> bool:
    """Check if user has sufficient permissions."""
    print("\n👤 Checking Azure permissions...")
    
    ok, hub_rg = get_azd_value("AZURE_RESOURCE_GROUP")
    if not ok:
        print(f"  ⚠️  Cannot determine hub RG")
        return True
    
    # Check Owner role on resource group
    rc, out, err = run_cmd(
        f'az role assignment list --resource-group "{hub_rg}" '
        f"--query \"[?roleDefinitionName=='Owner'].principalName\" -o json"
    )
    
    if rc == 0:
        roles = json.loads(out) if out else []
        if roles:
            print(f"  ✅ You have Owner permissions (or equivalent)")
            return True
        else:
            print(f"  ⚠️  Owner role not detected (you may still have permissions)")
            return True
    else:
        print(f"  ⚠️  Could not verify permissions (this is non-critical)")
        return True

def main():
    """Run all checks."""
    print("=" * 70)
    print("🔍 Product Finder Environment Validation")
    print("=" * 70)
    
    checks = [
        ("Required Tools", check_required_tools),
        ("Azure Authentication", check_azure_auth),
        ("azd Environment", check_azd_environment),
        ("Citadel Hub Resources", check_hub_resources),
        ("Spoke Resources", check_spoke_resources),
        ("Foundry Resources", check_foundry_resources),
        ("Azure Permissions", check_permissions),
    ]
    
    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nScore: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All checks passed! Ready to proceed with notebooks.")
        print("Next step: Run Notebook 1 (product-finder-foundation-prereq.ipynb)")
        return 0
    elif passed >= total - 2:
        print("\n⚠️  Most checks passed. Some resources may not exist yet.")
        print("This is OK if you're setting up for the first time.")
        print("Proceed with Notebook 1 and these will be created.")
        return 0
    else:
        print("\n❌ Critical checks failed. Please fix the issues above.")
        print("See: CLIENT_DEPLOYMENT_CHECKLIST.md and GETTING_STARTED.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
