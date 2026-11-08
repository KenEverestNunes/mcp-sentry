from mcp_sentry.fuzzing.payloads import MALICIOUS_PAYLOADS
from mcp_sentry.fuzzing.generators import DEFAULT_VALUES
from .generators import generate_edge_cases
from ..client import MCPClient
from ..config import TargetConfig
from ..models import FuzzCase

class FuzzEngine:
    async def run(self, client: MCPClient, config: TargetConfig) -> list[FuzzCase]:
        fuzz_cases = []
        tools = await client.discover_tools()
        
        for tool in tools:
            cases = generate_edge_cases(tool.input_schema) 
            properties = tool.input_schema.get("properties", {})

            baseline = {}
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get("type")
                baseline[prop_name] = DEFAULT_VALUES.get(prop_type)

            for prop_name, prop_schema in properties.items():
                if prop_schema.get("type") == "string":
                    for category, payloads in MALICIOUS_PAYLOADS.items():
                        for payload in payloads:
                            case = baseline.copy()
                            case[prop_name] = payload
                            cases.append(case)
        
            if not cases:
                cases = [{}]  
        
            for case_args in cases:
                result = await client.call_tool(tool.name, case_args)
                fuzz_cases.append(FuzzCase(tool_name=tool.name, arguments=case_args, result=result))
        
        return fuzz_cases