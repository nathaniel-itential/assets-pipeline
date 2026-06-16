#!/usr/bin/env python3
"""
Deployment script for promoting Itential integration models using asyncplatform.

Reads OpenAPI spec files listed in SPECS_FILE (default: /tmp/specs.txt) and
imports each as an integration model into the target Itential Platform environment.
The importer handles delete-before-replace and the 15 MB size limit automatically.

Usage:
    python deploy_integrations.py <environment>

Required environment variables:
    HOST              - Itential Platform hostname
    CLIENT_ID         - OAuth service account client ID
    CLIENT_SECRET     - OAuth service account client secret

Optional environment variables:
    SPECS_FILE        - Path to file listing spec paths (default: /tmp/specs.txt)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import asyncplatform


class IntegrationDeployer:
    """Handles deployment of integration models to a target environment."""

    def __init__(self, environment: str):
        """Initialize deployer with environment configuration.

        Args:
            environment: Target environment name
        """
        self.environment = environment
        self.host = os.environ.get("HOST")
        self.client_id = os.environ.get("CLIENT_ID")
        self.client_secret = os.environ.get("CLIENT_SECRET")
        self.specs_file = Path(os.environ.get("SPECS_FILE", "/tmp/specs.txt"))

        if not all([self.host, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing required environment variables: "
                "HOST, CLIENT_ID, CLIENT_SECRET"
            )

        print(f"🚀 Deploying integrations to {environment} environment")

    def find_spec_files(self) -> list[Path]:
        """Read spec file paths from SPECS_FILE.

        Returns:
            List of Path objects for each spec file listed
        """
        if not self.specs_file.exists():
            print(f"ℹ️  No specs file found at {self.specs_file}")
            return []

        specs = []
        for line in self.specs_file.read_text().splitlines():
            line = line.strip()
            if line:
                specs.append(Path(line))
                print(f"📦 Found spec: {Path(line).name}")

        return specs

    async def deploy_integration_models(
        self, client: Any, spec_files: list[Path]
    ) -> None:
        """Deploy integration models to the platform.

        Args:
            client: Asyncplatform client instance
            spec_files: List of OpenAPI spec file paths
        """
        if not spec_files:
            print("ℹ️  No integration specs to deploy")
            return

        integration_models = client.resource("integration_models")

        for spec_file in spec_files:
            with open(spec_file) as f:
                spec = json.load(f)

            title = spec.get("info", {}).get("title", spec_file.stem)
            version = spec.get("info", {}).get("version", "unknown")
            version_id = f"{title}:{version}"

            try:
                print(f"📥 Importing integration model: {version_id}")
                result = await integration_models.importer(spec)
                print(f"✅ Successfully imported: {result.get('name', version_id)}")
            except Exception as e:
                print(f"❌ Failed to import {version_id}: {e}")
                raise

    async def deploy(self) -> None:
        """Execute the deployment process."""
        print(f"\n{'='*60}")
        print(f"Starting integration deployment to {self.environment}")
        print(f"{'='*60}\n")

        spec_files = self.find_spec_files()
        if not spec_files:
            print("⚠️  No integration specs found to deploy")
            return

        async with asyncplatform.client(
            host=self.host,
            client_id=self.client_id,
            client_secret=self.client_secret,
            verify=True,
        ) as client:
            print(f"\n✅ Connected to Itential Platform: {self.host}\n")
            await self.deploy_integration_models(client, spec_files)

        print(f"\n{'='*60}")
        print(f"✅ Integration deployment to {self.environment} completed successfully!")
        print(f"{'='*60}\n")


def main():
    """Main entry point for the deployment script."""
    if len(sys.argv) != 2:
        print("Usage: python deploy_integrations.py <environment>")
        sys.exit(1)

    environment = sys.argv[1]

    try:
        deployer = IntegrationDeployer(environment)
        asyncio.run(deployer.deploy())
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
