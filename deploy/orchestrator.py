"""
Deployment Orchestrator - Manages deployment strategies and execution.

BUG INVENTORY:
- BUG-050: Rollback doesn't restore environment variables
- BUG-051: Blue-green deployment switch not atomic
- BUG-052: Health check timeout too aggressive
- BUG-053: Deployment log not persisted on crash
"""

import time
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class DeploymentStrategy(Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"


class DeploymentStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    HEALTH_CHECK = "health_check"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Deployment:
    def __init__(self, deploy_id: str, service: str, version: str,
                 strategy: DeploymentStrategy, environment: str):
        self.deploy_id = deploy_id
        self.service = service
        self.version = version
        self.previous_version = None
        self.strategy = strategy
        self.environment = environment
        self.status = DeploymentStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.health_check_passed = False
        self.logs: List[str] = []
        self.env_vars: Dict[str, str] = {}
        self.previous_env_vars: Dict[str, str] = {}


class DeploymentOrchestrator:
    """Orchestrates deployments across environments."""

    def __init__(self):
        self.deployments: List[Deployment] = []
        self.active_versions: Dict[str, str] = {}
        self.active_env_vars: Dict[str, Dict[str, str]] = {}
        self._deploy_counter = 0

    def deploy(self, service: str, version: str,
               strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
               environment: str = "production",
               env_vars: Dict[str, str] = None) -> Deployment:
        """
        Execute a deployment.

        BUG-053: Logs stored in memory only - lost on process crash.
        """
        self._deploy_counter += 1
        deploy_id = f"DEPLOY-{self._deploy_counter:06d}"

        deployment = Deployment(deploy_id, service, version, strategy, environment)
        deployment.previous_version = self.active_versions.get(service)
        deployment.env_vars = env_vars or {}
        deployment.previous_env_vars = dict(
            self.active_env_vars.get(service, {})
        )

        deployment.started_at = datetime.utcnow()
        deployment.status = DeploymentStatus.IN_PROGRESS
        # BUG-053: Log only in memory
        deployment.logs.append(f"[{datetime.utcnow()}] Starting deployment {deploy_id}")

        try:
            if strategy == DeploymentStrategy.BLUE_GREEN:
                self._blue_green_deploy(deployment)
            elif strategy == DeploymentStrategy.ROLLING:
                self._rolling_deploy(deployment)
            elif strategy == DeploymentStrategy.CANARY:
                self._canary_deploy(deployment)
            else:
                self._recreate_deploy(deployment)

            # Run health check
            deployment.status = DeploymentStatus.HEALTH_CHECK
            if self._health_check(deployment):
                deployment.health_check_passed = True
                deployment.status = DeploymentStatus.COMPLETED
                self.active_versions[service] = version
                self.active_env_vars[service] = deployment.env_vars
            else:
                deployment.status = DeploymentStatus.FAILED
                deployment.logs.append(f"[{datetime.utcnow()}] Health check failed")

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.logs.append(f"[{datetime.utcnow()}] Error: {str(e)}")

        deployment.completed_at = datetime.utcnow()
        self.deployments.append(deployment)
        return deployment

    def _blue_green_deploy(self, deployment: Deployment):
        """
        Blue-green deployment.

        BUG-051: Traffic switch from blue to green is not atomic.
        Brief period where both or neither environments serve traffic.
        """
        deployment.logs.append("Starting blue-green deployment")

        # Start green environment
        deployment.logs.append("Green environment starting...")
        time.sleep(0.01)

        # BUG-051: Non-atomic switch
        # Step 1: Remove blue from load balancer
        deployment.logs.append("Removing blue from load balancer")
        time.sleep(0.005)  # Gap where NO environment serves traffic

        # Step 2: Add green to load balancer
        deployment.logs.append("Adding green to load balancer")
        # Between step 1 and 2, requests may fail

    def _rolling_deploy(self, deployment: Deployment):
        """Rolling deployment - update instances one by one."""
        instances = 4
        for i in range(instances):
            deployment.logs.append(f"Updating instance {i+1}/{instances}")
            time.sleep(0.005)

    def _canary_deploy(self, deployment: Deployment):
        """Canary deployment - gradual traffic shift."""
        for pct in [5, 25, 50, 100]:
            deployment.logs.append(f"Canary at {pct}% traffic")
            time.sleep(0.005)

    def _recreate_deploy(self, deployment: Deployment):
        """Recreate - stop all, then start new."""
        deployment.logs.append("Stopping all instances")
        time.sleep(0.01)
        deployment.logs.append("Starting new version")

    def _health_check(self, deployment: Deployment) -> bool:
        """
        BUG-052: Only waits 2 seconds for health check.
        Some services need 30+ seconds to initialize.
        """
        # BUG-052: Aggressive timeout
        max_retries = 2  # Should be 10+
        retry_delay = 1  # Should be 5+

        for attempt in range(max_retries):
            # Simulate health check (succeeds 80% of time)
            if (self._deploy_counter + attempt) % 5 != 0:
                return True
            time.sleep(0.01)  # Simulated

        return False

    def rollback(self, deploy_id: str) -> bool:
        """
        Rollback to previous version.

        BUG-050: Restores version but NOT environment variables.
        Service runs with new config on old code = potential crash.
        """
        target = None
        for d in self.deployments:
            if d.deploy_id == deploy_id:
                target = d
                break

        if not target or not target.previous_version:
            return False

        # Restore version
        self.active_versions[target.service] = target.previous_version

        # BUG-050: Environment variables NOT restored
        # Missing: self.active_env_vars[target.service] = target.previous_env_vars

        target.status = DeploymentStatus.ROLLED_BACK
        target.logs.append(f"[{datetime.utcnow()}] Rolled back to {target.previous_version}")
        return True

    def get_deployment_history(self, service: str = None) -> List[dict]:
        """Get deployment history."""
        deployments = self.deployments
        if service:
            deployments = [d for d in deployments if d.service == service]

        return [
            {
                "deploy_id": d.deploy_id,
                "service": d.service,
                "version": d.version,
                "strategy": d.strategy.value,
                "status": d.status.value,
                "environment": d.environment,
                "started_at": d.started_at.isoformat() if d.started_at else None,
                "completed_at": d.completed_at.isoformat() if d.completed_at else None,
            }
            for d in deployments
        ]
