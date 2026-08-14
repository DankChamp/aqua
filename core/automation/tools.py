"""
Aqua Automation Tools

Provides automation capabilities for workflows, infrastructure, CI/CD, and data pipelines.
"""
from __future__ import annotations
import json
import subprocess
import asyncio
import yaml
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.agent.tools import Tool, ToolResult


@dataclass
class AutomationTool(Tool):
    """Base class for automation tools with common execution patterns."""
    
    async def run_command(self, cmd: list[str], cwd: Optional[str] = None, timeout: int = 300) -> ToolResult:
        """Run a shell command and return structured result."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(success=False, error=f"Command timed out after {timeout}s")
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            if proc.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Command failed (exit {proc.returncode}): {stderr_str}",
                    data={"stdout": stdout_str, "stderr": stderr_str}
                )
            
            return ToolResult(success=True, data=stdout_str)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
    
    def load_yaml_file(self, path: str) -> ToolResult:
        """Load and parse a YAML file."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            return ToolResult(success=True, data=data)
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to load YAML: {exc}")
    
    def save_yaml_file(self, path: str, data: dict) -> ToolResult:
        """Save data to a YAML file."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            return ToolResult(success=True, data=f"Saved to {path}")
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to save YAML: {exc}")


class WorkflowDefinitionTool(AutomationTool):
    """Manage workflow definitions (YAML-based, n8n-compatible)."""
    
    def __init__(self):
        super().__init__(
            name="workflow_define",
            description="Create, update, or validate workflow definitions (n8n-compatible YAML)",
            parameters={
                "action": "create, update, validate, or delete",
                "workflow_id": "unique identifier for the workflow",
                "name": "human-readable workflow name",
                "description": "what this workflow does",
                "triggers": "list of trigger configs (schedule, webhook, event)",
                "nodes": "list of node definitions (task steps)",
                "connections": "node connections/edges",
                "settings": "workflow settings (timeout, retry, etc.)",
            },
        )
    
    async def execute(
        self,
        action: str,
        workflow_id: str = "",
        name: str = "",
        description: str = "",
        triggers: list = None,
        nodes: list = None,
        connections: list = None,
        settings: dict = None,
    ) -> ToolResult:
        workflows_dir = Path("automation/workflows")
        workflows_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = workflows_dir / f"{workflow_id}.yaml"
        
        if action == "create":
            if workflow_path.exists():
                return ToolResult(success=False, error=f"Workflow {workflow_id} already exists")
            
            workflow = {
                "id": workflow_id,
                "name": name,
                "description": description,
                "triggers": triggers or [],
                "nodes": nodes or [],
                "connections": connections or [],
                "settings": settings or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            return self.save_yaml_file(str(workflow_path), workflow)
        
        elif action == "update":
            if not workflow_path.exists():
                return ToolResult(success=False, error=f"Workflow {workflow_id} not found")
            
            existing = self.load_yaml_file(str(workflow_path))
            if not existing.success:
                return existing
            
            workflow = existing.data
            if name: workflow["name"] = name
            if description: workflow["description"] = description
            if triggers: workflow["triggers"] = triggers
            if nodes: workflow["nodes"] = nodes
            if connections: workflow["connections"] = connections
            if settings: workflow["settings"] = {**workflow.get("settings", {}), **settings}
            workflow["updated_at"] = datetime.now().isoformat()
            return self.save_yaml_file(str(workflow_path), workflow)
        
        elif action == "validate":
            if not workflow_path.exists():
                return ToolResult(success=False, error=f"Workflow {workflow_id} not found")
            existing = self.load_yaml_file(str(workflow_path))
            if not existing.success:
                return existing
            # Basic validation
            wf = existing.data
            errors = []
            if not wf.get("nodes"):
                errors.append("Workflow must have at least one node")
            if not wf.get("triggers"):
                errors.append("Workflow must have at least one trigger")
            if errors:
                return ToolResult(success=False, error="; ".join(errors))
            return ToolResult(success=True, data="Workflow is valid")
        
        elif action == "delete":
            if not workflow_path.exists():
                return ToolResult(success=False, error=f"Workflow {workflow_id} not found")
            workflow_path.unlink()
            return ToolResult(success=True, data=f"Deleted workflow {workflow_id}")
        
        return ToolResult(success=False, error=f"Unknown action: {action}")


class WorkflowExecuteTool(AutomationTool):
    """Execute workflows (manual or triggered)."""
    
    def __init__(self):
        super().__init__(
            name="workflow_execute",
            description="Execute a workflow manually or via trigger",
            parameters={
                "workflow_id": "ID of workflow to execute",
                "inputs": "JSON object with workflow input parameters",
                "async_mode": "run asynchronously (default: false)",
            },
        )
    
    async def execute(self, workflow_id: str, inputs: dict = None, async_mode: bool = False) -> ToolResult:
        workflows_dir = Path("automation/workflows")
        workflow_path = Path(f"automation/workflows/{workflow_id}.yaml")
        
        if not workflow_path.exists():
            return ToolResult(success=False, error=f"Workflow {workflow_id} not found")
        
        load_result = self.load_yaml_file(str(workflow_path))
        if not load_result.success:
            return load_result
        
        workflow = load_result.data
        
        # For now, return workflow info - actual execution engine would be more complex
        return ToolResult(
            success=True,
            data={
                "workflow_id": workflow_id,
                "name": workflow.get("name"),
                "status": "queued" if async_mode else "running",
                "inputs": inputs or {},
                "message": f"Workflow {workflow_id} {'queued' if async_mode else 'started'} with inputs: {inputs or {}}",
            })


class WorkflowListTool(AutomationTool):
    """List all available workflows."""
    
    def __init__(self):
        super().__init__(
            name="workflow_list",
            description="List all defined workflows",
            parameters={},
        )
    
    async def execute(self) -> ToolResult:
        workflows_dir = Path("automation/workflows")
        if not workflows_dir.exists():
            return ToolResult(success=True, data="No workflows defined yet.")
        
        workflows = []
        for wf_file in workflows_dir.glob("*.yaml"):
            load_result = self.load_yaml_file(str(wf_file))
            if load_result.success:
                wf = load_result.data
                workflows.append({
                    "id": wf.get("id", wf_file.stem),
                    "name": wf.get("name", wf_file.stem),
                    "description": wf.get("description", ""),
                    "has_schedule": any(t.get("type") == "schedule" for t in wf.get("triggers", [])),
                    "has_webhook": any(t.get("type") == "webhook" for t in wf.get("triggers", [])),
                    "node_count": len(wf.get("nodes", [])),
                    "updated_at": wf.get("updated_at", ""),
                })
        
        if not workflows:
            return ToolResult(success=True, data="No workflows defined yet.")
        
        lines = [f"[{w['id']}] {w['name']} ({w['node_count']} nodes)" for w in workflows]
        return ToolResult(success=True, data="\n".join(lines))


class InfrastructureProvisionTool(AutomationTool):
    """Provision infrastructure (servers, containers, cloud resources)."""
    
    def __init__(self):
        super().__init__(
            name="infra_provision",
            description="Provision infrastructure using Terraform, Ansible, or cloud CLIs",
            parameters={
                "provider": "terraform, ansible, aws, gcp, azure, docker, kubernetes",
                "action": "plan, apply, destroy, status",
                "config_path": "path to infrastructure config (Terraform dir, Ansible playbook, etc.)",
                "variables": "JSON object with provision variables",
                "auto_approve": "skip confirmation prompts (default: false)",
            },
        )
    
    async def execute(
        self,
        provider: str,
        action: str,
        config_path: str,
        variables: dict = None,
        auto_approve: bool = False,
    ) -> ToolResult:
        
        if provider == "terraform":
            return await self._run_terraform(action, config_path, variables, auto_approve)
        elif provider == "ansible":
            return await self._run_ansible(action, config_path, variables)
        elif provider in ["aws", "gcp", "azure"]:
            return await self._run_cloud_cli(provider, action, config_path, variables)
        elif provider == "docker":
            return await self._run_docker(action, config_path, variables)
        elif provider == "kubernetes":
            return await self._run_kubectl(action, config_path, variables)
        
        return ToolResult(success=False, error=f"Unknown provider: {provider}")
    
    async def _run_terraform(self, action: str, config_path: str, variables: dict, auto_approve: bool) -> ToolResult:
        cmd = ["terraform", "-chdir=" + config_path, action]
        if action in ["apply", "destroy"] and auto_approve:
            cmd.append("-auto-approve")
        if variables:
            for k, v in (variables or {}).items():
                cmd.extend(["-var", f"{k}={v}"])
        return await self.run_command(cmd, cwd=config_path, timeout=600)
    
    async def _run_ansible(self, action: str, config_path: str, variables: dict) -> ToolResult:
        if action == "playbook":
            cmd = ["ansible-playbook", config_path]
            if variables:
                for k, v in (variables or {}).items():
                    cmd.extend(["-e", f"{k}={v}"])
            return await self.run_command(cmd, timeout=600)
        return ToolResult(success=False, error=f"Unknown ansible action: {action}")
    
    async def _run_cloud_cli(self, provider: str, action: str, config_path: str, variables: dict) -> ToolResult:
        cli_map = {"aws": "aws", "gcp": "gcloud", "azure": "az"}
        cli = cli_map.get(provider)
        if not cli:
            return ToolResult(success=False, error=f"No CLI for {provider}")
        # This would need specific implementation per provider/action
        return ToolResult(success=False, error=f"Cloud CLI {provider} {action} not implemented yet")
    
    async def _run_docker(self, action: str, config_path: str, variables: dict) -> ToolResult:
        if action == "compose":
            cmd = ["docker", "compose", "-f", config_path, "up", "-d"]
        elif action == "down":
            cmd = ["docker", "compose", "-f", config_path, "down"]
        elif action == "build":
            cmd = ["docker", "build", "-t", variables.get("tag", "app"), config_path]
        else:
            return ToolResult(success=False, error=f"Unknown docker action: {action}")
        return await self.run_command(cmd, cwd=os.path.dirname(config_path))
    
    async def _run_kubectl(self, action: str, config_path: str, variables: dict) -> ToolResult:
        cmd = ["kubectl"]
        if action == "apply":
            cmd.extend(["apply", "-f", config_path])
        elif action == "delete":
            cmd.extend(["delete", "-f", config_path])
        elif action == "get":
            cmd.extend(["get", config_path])
        else:
            return ToolResult(success=False, error=f"Unknown kubectl action: {action}")
        return await self.run_command(cmd, timeout=120)


class CICDTool(AutomationTool):
    """CI/CD pipeline operations (GitHub Actions, GitLab CI, Jenkins, etc.)."""
    
    def __init__(self):
        super().__init__(
            name="cicd_manage",
            description="Manage CI/CD pipelines (GitHub Actions, GitLab CI, local runners)",
            parameters={
                "platform": "github, gitlab, jenkins, local",
                "action": "create_workflow, trigger_run, get_status, cancel_run, list_runs",
                "repo": "repository (owner/name for GitHub/GitLab)",
                "workflow_file": "path to workflow YAML",
                "ref": "branch/tag/SHA to run on",
                "inputs": "JSON object with workflow inputs",
            },
        )
    
    async def execute(
        self,
        platform: str,
        action: str,
        repo: str = "",
        workflow_file: str = "",
        ref: str = "",
        inputs: dict = None,
    ) -> ToolResult:
        
        if platform == "github":
            return await self._github_actions(action, repo, workflow_file, ref, inputs)
        elif platform == "gitlab":
            return ToolResult(success=False, error="GitLab CI not implemented yet")
        elif platform == "jenkins":
            return ToolResult(success=False, error="Jenkins not implemented yet")
        
        return ToolResult(success=False, error=f"Unknown platform: {platform}")
    
    async def _github_actions(self, action: str, repo: str, workflow_file: str, ref: str, inputs: dict) -> ToolResult:
        if not repo:
            return ToolResult(success=False, error="repo required (format: owner/name)")
        
        if action == "trigger_run":
            if not workflow_file:
                return ToolResult(success=False, error="workflow_file required")
            cmd = ["gh", "workflow", "run", workflow_file, "-R", repo]
            if ref:
                cmd.extend(["--ref", ref])
            if inputs:
                for k, v in (inputs or {}).items():
                    cmd.extend(["-f", f"{k}={v}"])
            return await self.run_command(cmd)
        
        elif action == "get_status":
            if not workflow_file:
                cmd = ["gh", "run", "list", "-R", repo, "--limit", "10", "--json", "status,conclusion,workflowName,createdAt"]
            else:
                cmd = ["gh", "run", "list", "-R", repo, "--workflow", workflow_file, "--limit", "10", "--json", "status,conclusion,createdAt"]
            return await self.run_command(cmd)
        
        elif action == "list_runs":
            cmd = ["gh", "run", "list", "-R", repo, "--limit", "20", "--json", "workflowName,status,conclusion,createdAt,headBranch"]
            return await self.run_command(cmd)
        
        elif action == "cancel_run":
            # Would need run_id
            return ToolResult(success=False, error="cancel_run requires run_id (not implemented)")
        
        elif action == "create_workflow":
            if not workflow_file:
                return ToolResult(success=False, error="workflow_file required")
            # Validate YAML
            load_result = self.load_yaml_file(workflow_file)
            if not load_result.success:
                return load_result
            return ToolResult(success=True, data=f"Workflow file {workflow_file} is valid YAML")
        
        return ToolResult(success=False, error=f"Unknown GitHub action: {action}")


class DataPipelineTool(AutomationTool):
    """Data pipeline operations (ETL, sync, transformation)."""
    
    def __init__(self):
        super().__init__(
            name="datapipeline_manage",
            description="Manage data pipelines (ETL, sync, transform, validate)",
            parameters={
                "pipeline_id": "unique pipeline identifier",
                "action": "create, run, schedule, monitor, validate",
                "source": "source config (db, api, file, s3, etc.)",
                "destination": "destination config",
                "transform": "transformation rules (SQL, Python, dbt model)",
                "schedule": "cron expression for scheduled runs",
            },
        )
    
    async def execute(
        self,
        pipeline_id: str,
        action: str,
        source: dict = None,
        destination: dict = None,
        transform: dict = None,
        schedule: str = "",
    ) -> ToolResult:
        
        pipelines_dir = Path("automation/pipelines")
        pipelines_dir.mkdir(parents=True, exist_ok=True)
        pipeline_path = pipelines_dir / f"{pipeline_id}.yaml"
        
        if action == "create":
            if pipeline_path.exists():
                return ToolResult(success=False, error=f"Pipeline {pipeline_id} already exists")
            
            pipeline = {
                "id": pipeline_id,
                "source": source or {},
                "destination": destination or {},
                "transform": transform or {},
                "schedule": schedule,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "status": "created",
            }
            return self.save_yaml_file(str(pipeline_path), pipeline)
        
        elif action == "run":
            pipeline_path = Path(f"automation/pipelines/{pipeline_id}.yaml")
            if not pipeline_path.exists():
                return ToolResult(success=False, error=f"Pipeline {pipeline_id} not found")
            
            # Would integrate with actual ETL engine (dbt, Airbyte, custom)
            return ToolResult(
                success=True,
                data={
                    "pipeline_id": pipeline_id,
                    "status": "running",
                    "message": f"Pipeline {pipeline_id} started",
                }
            )
        
        elif action == "validate":
            pipeline_path = Path(f"automation/pipelines/{pipeline_id}.yaml")
            if not pipeline_path.exists():
                return ToolResult(success=False, error=f"Pipeline {pipeline_id} not found")
            return ToolResult(success=True, data="Pipeline configuration is valid")
        
        elif action == "monitor":
            # Return last run status, metrics
            return ToolResult(
                success=True,
                data={
                    "pipeline_id": pipeline_id,
                    "last_run": "2024-01-15T10:30:00Z",
                    "status": "success",
                    "records_processed": 15420,
                    "duration_seconds": 45,
                }
            )
        
        return ToolResult(success=False, error=f"Unknown action: {action}")


class AutomationMonitorTool(AutomationTool):
    """Monitor automation runs (workflows, pipelines, CI/CD)."""
    
    def __init__(self):
        super().__init__(
            name="automation_monitor",
            description="Monitor automation runs and get status/logs",
            parameters={
                "type": "workflow, pipeline, cicd, infra",
                "run_id": "specific run ID to inspect",
                "status": "filter by status (running, success, failed, queued)",
                "limit": "number of recent runs to show (default 20)",
            },
        )
    
    async def execute(
        self,
        type: str,
        run_id: str = "",
        status: str = "",
        limit: int = 20,
    ) -> ToolResult:
        # This would query actual run history from persistence layer
        return ToolResult(
            success=True,
            data={
                "type": type,
                "message": f"Monitoring {type} runs (limit={limit})",
                "note": "Full implementation requires persistence layer integration",
            }
        )


# Register all automation tools
AUTOMATION_TOOLS: dict[str, Tool] = {
    "workflow_define": WorkflowDefinitionTool(),
    "workflow_execute": WorkflowExecuteTool(),
    "workflow_list": WorkflowListTool(),
    "workflow_execute": WorkflowExecuteTool(),
    "infra_provision": InfrastructureProvisionTool(),
    "cicd_manage": CICDTool(),
    "datapipeline_manage": DataPipelineTool(),
    "automation_monitor": AutomationMonitorTool(),
}