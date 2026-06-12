#!/usr/bin/env python3
"""
Integration model deployment and role management script.

Imports OpenAPI-based integration models into Itential Platform via ipctl,
then assigns the auto-created integration roles to a target group so that
access is consistent across environments.

Usage:
    python deploy_integrations.py <environment>

Required environment variables:
    HOST              - Itential Platform hostname
    CLIENT_ID         - OAuth service account client ID
    CLIENT_SECRET     - OAuth service account client secret

Optional environment variables:
    INTEGRATION_GROUP - Group name to assign integration roles to (skips role
                        management if not set)
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import asyncplatform


class IntegrationDeployer:
    """Handles integration model deployment and role management."""

    def __init__(self, environment: str):
        self.environment = environment
        self.host = os.environ.get("HOST")
        self.client_id = os.environ.get("CLIENT_ID")
        self.client_secret = os.environ.get("CLIENT_SECRET")
        self.integration_group = os.environ.get("INTEGRATION_GROUP")

        if not all([self.host, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing required environment variables: HOST, CLIENT_ID, CLIENT_SECRET"
            )

        print(f"🚀 Deploying integrations to {environment} environment")

    def _write_ipctl_config(self) -> str:
        """Write a temporary ipctl config file and return its path."""
        config_content = (
            "[profile default]\n"
            f"host = {self.host}\n"
            "port = 0\n"
            "use_tls = true\n"
            f"client_id = {self.client_id}\n"
            f"client_secret = {self.client_secret}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(config_content)
            return f.name

    def find_integration_files(self) -> list[Path]:
        """Scan repository for OpenAPI integration spec files."""
        repo_root = Path.cwd()
        files = list(repo_root.glob("**/OpenAPIs/*.json"))
        for f in files:
            print(f"🔌 Found integration: {f.name}")
        return files

    def _list_existing_models(self, env: dict) -> list[dict]:
        """Return all integration models currently on the platform."""
        result = subprocess.run(
            ["ipctl", "get", "integration-models", "--output", "json"],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return []
        try:
            return json.loads(result.stdout).get("integrationModels", [])
        except (json.JSONDecodeError, AttributeError):
            return []

    def _delete_existing_model(self, spec_path: Path, env: dict) -> None:
        """Delete the platform model whose versionId matches the spec's title:version.

        ipctl's --replace flag is unimplemented for integration-model imports — the
        runner calls service.Create() directly with no delete-first logic, so the
        platform returns 500 when the title+version already exists. We handle
        replacement ourselves by deleting before importing.
        """
        with open(spec_path) as f:
            spec = json.load(f)

        title = spec.get("info", {}).get("title", "")
        version = spec.get("info", {}).get("version", "")
        target_version_id = f"{title}:{version}"

        models = self._list_existing_models(env)
        match = next((m for m in models if m.get("versionId") == target_version_id), None)

        if not match:
            return

        model_name = match.get("model") or match.get("versionId")
        print(f"🗑️  Deleting existing model: {model_name}")
        subprocess.run(
            ["ipctl", "delete", "integration-model", model_name],
            env=env, capture_output=True, text=True, check=True,
        )

    def deploy_integrations(self, integration_files: list[Path], env: dict) -> list[str]:
        """Import integration models via ipctl.

        Returns:
            List of successfully imported integration names.
        """
        if not integration_files:
            print("ℹ️  No integrations to deploy")
            return []

        imported = []
        for integration_file in integration_files:
            integration_name = integration_file.stem
            try:
                self._delete_existing_model(integration_file, env)
                print(f"📥 Importing integration: {integration_name}")
                result = subprocess.run(
                    ["ipctl", "import", "integration-model", str(integration_file), "--verbose"],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if result.stdout:
                    print(result.stdout.strip())
                print(f"✅ Successfully imported integration: {integration_name}")
                imported.append(integration_name)
            except subprocess.CalledProcessError as e:
                output = "\n".join(
                    filter(None, [
                        e.stdout.strip() if e.stdout else None,
                        e.stderr.strip() if e.stderr else None,
                    ])
                )
                if output:
                    print(output)
                print(f"⚠️  Skipping integration {integration_name} (exit code {e.returncode})")

        return imported

    def create_integration_instances(self, integration_files: list[Path], env: dict) -> None:
        """Create an integration instance for each model if one doesn't exist.

        The instance name is the file stem. The --model argument must be the
        platform's versionId (info.title:info.version from the OpenAPI spec),
        not the filename — the platform identifies models by that key.
        Skips creation if an instance already exists to avoid overwriting config.
        """
        if not integration_files:
            return

        for integration_file in integration_files:
            name = integration_file.stem

            with open(integration_file) as f:
                spec = json.load(f)
            title = spec.get("info", {}).get("title", "")
            version = spec.get("info", {}).get("version", "")
            version_id = f"{title}:{version}"

            # Check if an instance already exists
            check = subprocess.run(
                ["ipctl", "describe", "integration", name],
                env=env,
                capture_output=True,
                text=True,
            )
            if check.returncode == 0:
                print(f"ℹ️  Integration instance already exists, skipping: {name}")
                continue

            try:
                print(f"🔧 Creating integration instance: {name} (model: {version_id})")
                result = subprocess.run(
                    ["ipctl", "create", "integration", name, "--model", version_id],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if result.stdout:
                    print(result.stdout.strip())
                print(f"✅ Created integration instance: {name}")
            except subprocess.CalledProcessError as e:
                output = "\n".join(
                    filter(None, [
                        e.stdout.strip() if e.stdout else None,
                        e.stderr.strip() if e.stderr else None,
                    ])
                )
                if output:
                    print(output)
                print(f"⚠️  Could not create integration instance {name} (exit code {e.returncode})")

    async def manage_roles(self, client: Any, imported_names: list[str]) -> None:
        """Assign auto-created integration roles to the target group.

        After an integration model is imported, the platform auto-creates roles
        for it. This method queries those roles by name and adds them to
        INTEGRATION_GROUP so access is consistent across environments.
        """
        if not self.integration_group:
            print("ℹ️  INTEGRATION_GROUP not set — skipping role management")
            return

        if not imported_names:
            print("ℹ️  No integration files found — skipping role management")
            return

        print(f"\n🔐 Assigning integration roles to group: {self.integration_group}")

        # Fetch roles sorted by _id descending — auto-created roles are newest and land on page 1.
        # API caps at 100 per page regardless of limit value.
        res = await client.authorization.get(
            "/authorization/roles",
            params={"skip": 0, "limit": 100, "sort": "_id", "order": -1},
        )
        all_roles = res.json().get("results", [])

        # Auto-created roles have provenance = versionId (title:version).
        # Role names are HTTP verb types (admin, get, post, put, patch, delete).
        provenance_set = set(imported_names)
        integration_roles = [r for r in all_roles if r.get("provenance") in provenance_set]

        if not integration_roles:
            print(
                f"⚠️  No roles found with provenance matching: {list(provenance_set)}\n"
                "    Verify auto-created role provenance matches the integration versionId."
            )
            return

        # Find the target group by name — ID is resolved per-environment
        groups = await client.authorization.get_groups()
        group = next((g for g in groups if g["name"] == self.integration_group), None)

        if not group:
            print(f"⚠️  Group '{self.integration_group}' not found — skipping role management")
            return

        # assignedRoles is [{roleId: ...}] — extract IDs for comparison
        existing_ids: set[str] = {r["roleId"] for r in group.get("assignedRoles", [])}
        new_ids: set[str] = {r["_id"] for r in integration_roles}

        if new_ids <= existing_ids:
            print(f"ℹ️  All integration roles already assigned to '{self.integration_group}'")
            return

        # PATCH requires {updates: {assignedRoles: [{roleId: ...}]}} wrapper
        merged = [{"roleId": rid} for rid in existing_ids | new_ids]
        await client.authorization.patch(
            f"/authorization/groups/{group['_id']}",
            json={"updates": {"assignedRoles": merged}},
        )

        for role in integration_roles:
            if role["_id"] not in existing_ids:
                print(f"✅ Assigned role '{role['name']}' ({role.get('provenance')}) to group '{self.integration_group}'")

    async def run(self) -> None:
        print(f"\n{'='*60}")
        print(f"Starting integration deployment to {self.environment}")
        print(f"{'='*60}\n")

        integration_files = self.find_integration_files()

        if not integration_files:
            print("⚠️  No integration files found — skipping")
            return

        config_file = self._write_ipctl_config()
        ipctl_env = os.environ.copy()
        ipctl_env["IPCTL_CONFIG_FILE"] = config_file

        try:
            imported_names = self.deploy_integrations(integration_files, ipctl_env)
            self.create_integration_instances(integration_files, ipctl_env)
            all_names = []
            for f in integration_files:
                with open(f) as spec_f:
                    spec = json.load(spec_f)
                info = spec.get("info", {})
                title = info.get("title", f.stem)
                version = info.get("version", "")
                all_names.append(f"{title}:{version}" if version else title)
        finally:
            os.unlink(config_file)

        async with asyncplatform.client(
            host=self.host,
            client_id=self.client_id,
            client_secret=self.client_secret,
            verify=True,
        ) as client:
            await self.manage_roles(client, all_names)

        print(f"\n{'='*60}")
        print(f"✅ Integration deployment to {self.environment} completed")
        print(f"{'='*60}\n")


def main():
    if len(sys.argv) != 2:
        print("Usage: python deploy_integrations.py <environment>")
        sys.exit(1)

    try:
        deployer = IntegrationDeployer(sys.argv[1])
        asyncio.run(deployer.run())
    except Exception as e:
        print(f"\n❌ Integration deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
