"""
Aqua Automation API Routes

REST endpoints for managing workflows, pipelines, infrastructure, CI/CD, and data pipelines.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from core.automation.tools import AUTOMATION_TOOLS
from core.observability import get_metrics, MetricNames

router = APIRouter(prefix="/automation", tags=["automation"])


class ToolExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}


class AutomationCommandRequest(BaseModel):
    command: str
    context: Optional[Dict[str, Any]] = None


class WorkflowDefineRequest(BaseModel):
    action: str  # create, update, validate, delete
    workflow_id: str = ""
    name: str = ""
    description: str = ""
    triggers: List[Dict] = []
    nodes: List[Dict] = []
    connections: List[Dict] = []
    settings: Dict = {}


class InfraProvisionRequest(BaseModel):
    provider: str
    action: str
    config_path: str
    variables: Dict[str, Any] = {}
    auto_approve: bool = False


class CICDRequest(BaseModel):
    platform: str
    action: str
    repo: str = ""
    workflow_file: str = ""
    ref: str = ""
    inputs: Dict[str, Any] = {}


class PipelineRequest(BaseModel):
    pipeline_id: str
    action: str
    source: Dict = {}
    destination: Dict = {}
    transform: Dict = {}
    schedule: str = ""


@router.post("/tool/execute")
async def execute_tool(request: ToolExecuteRequest):
    """Execute an automation tool directly."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    
    if request.tool not in AUTOMATION_TOOLS:
        raise HTTPException(404, f"Tool '{request.tool}' not found. Available: {list(AUTOMATION_TOOLS.keys())}")
    
    tool = AUTOMATION_TOOLS[request.tool]
    metrics.increment(MetricNames.TOOL_EXECUTIONS, labels={"tool": request.tool})
    
    try:
        result = await tool.execute(**request.args)
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }
    except Exception as e:
        raise HTTPException(500, f"Tool execution failed: {str(e)}")


@router.post("/command")
async def execute_command(request: AutomationCommandRequest):
    """Execute a natural language automation command."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    metrics.increment(MetricNames.DELEGATION_STARTED, labels={"type": "automation"})
    
    # TODO: Implement natural language parsing for automation commands
    # For now, return a helpful response
    return {
        "success": True,
        "data": f"Automation command received: {request.command}",
        "note": "Natural language automation parsing is a work in progress. Use /tool/execute for direct tool access.",
        "available_tools": list(AUTOMATION_TOOLS.keys()),
    }


@router.post("/workflow")
async def workflow_manage(request: WorkflowDefineRequest):
    """Manage workflow definitions."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    metrics.increment(MetricNames.DELEGATION_STARTED, labels={"type": "workflow"})
    
    tool = AUTOMATION_TOOLS.get("workflow_define")
    if not tool:
        raise HTTPException(500, "Workflow tool not available")
    
    result = await tool.execute(
        action=request.action,
        workflow_id=request.workflow_id,
        name=request.name,
        description=request.description,
        triggers=request.triggers,
        nodes=request.nodes,
        connections=request.connections,
        settings=request.settings,
    )
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    return {"success": True, "data": result.data}


@router.get("/workflows")
async def list_workflows():
    """List all workflows."""
    tool = AUTOMATION_TOOLS.get("workflow_list")
    if not tool:
        raise HTTPException(500, "Workflow tool not available")
    
    result = await tool.execute()
    return {"success": result.success, "data": result.data}


@router.post("/workflow/execute")
async def execute_workflow(workflow_id: str, inputs: Dict = None, async_mode: bool = False):
    """Execute a workflow."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    metrics.increment(MetricNames.DELEGATION_STARTED, labels={"type": "workflow"})
    
    tool = AUTOMATION_TOOLS.get("workflow_execute")
    if not tool:
        raise HTTPException(500, "Workflow tool not available")
    
    result = await tool.execute(workflow_id=workflow_id, inputs=inputs or {}, async_mode=async_mode)
    return {"success": result.success, "data": result.data}


@router.post("/infrastructure")
async def infrastructure_manage(request: InfraProvisionRequest):
    """Provision infrastructure."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    metrics.increment(MetricNames.DELEGATION_STARTED, labels={"type": "infrastructure"})
    
    tool = AUTOMATION_TOOLS.get("infra_provision")
    if not tool:
        raise HTTPException(500, "Infrastructure tool not available")
    
    result = await tool.execute(
        provider=request.provider,
        action=request.action,
        config_path=request.config_path,
        variables=request.variables,
        auto_approve=request.auto_approve,
    )
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    return {"success": True, "data": result.data}


@router.post("/cicd")
async def cicd_manage(request: CICDRequest):
    """Manage CI/CD pipelines."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    metrics.increment(MetricNames.DELEGATION_STARTED, labels={"type": "cicd"})
    
    tool = AUTOMATION_TOOLS.get("cicd_manage")
    if not tool:
        raise HTTPException(500, "CI/CD tool not available")
    
    result = await tool.execute(
        platform=request.platform,
        action=request.action,
        repo=request.repo,
        workflow_file=request.workflow_file,
        ref=request.ref,
        inputs=request.inputs,
    )
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    return {"success": True, "data": result.data}


@router.post("/pipeline")
async def pipeline_manage(request: PipelineRequest):
    """Manage data pipelines."""
    from core.observability import get_metrics, MetricNames
    
    metrics = get_metrics()
    metrics.increment(MetricNames.DELEGATION_STARTED, labels={"type": "pipeline"})
    
    tool = AUTOMATION_TOOLS.get("datapipeline_manage")
    if not tool:
        raise HTTPException(500, "Pipeline tool not available")
    
    result = await tool.execute(
        pipeline_id=request.pipeline_id,
        action=request.action,
        source=request.source,
        destination=request.destination,
        transform=request.transform,
        schedule=request.schedule,
    )
    
    if not result.success:
        raise HTTPException(400, result.error)
    
    return {"success": True, "data": result.data}


@router.get("/monitor/{run_type}")
async def monitor_runs(
    run_type: str,
    run_id: str = "",
    status: str = "",
    limit: int = 20,
):
    """Monitor automation runs."""
    tool = AUTOMATION_TOOLS.get("automation_monitor")
    if not tool:
        raise HTTPException(500, "Monitor tool not available")
    
    result = await tool.execute(
        type=run_type,
        run_id=run_id,
        status=status,
        limit=limit,
    )
    
    return {"success": result.success, "data": result.data}


@router.get("/tools")
async def list_tools():
    """List all available automation tools."""
    return {
        "tools": {
            name: {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for name, tool in AUTOMATION_TOOLS.items()
        }
    }


@router.get("/health")
async def automation_health():
    """Health check for automation service."""
    return {
        "ok": True,
        "service": "aqua-automation",
        "tools_count": len(AUTOMATION_TOOLS),
        "tools": list(AUTOMATION_TOOLS.keys()),
    }