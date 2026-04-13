"""
Explicitly request specific safety dimensions.

Instead of letting the router auto-select, you can specify which
dimensions to check. Useful when you know your use case.
"""

import asyncio
import json
from fangcunguard_router import GuardRouter


async def main():
    router = GuardRouter("guard_models.yaml")

    text = "Send the quarterly revenue report to john@company.com with password abc123"

    # Auto mode - router decides
    print("Auto mode:")
    result = await router.check(text)
    print(f"  Dimensions: {result.routing_info['dimensions_requested']}")
    print(f"  Safe: {result.safe}")

    # Explicit - only check PII
    print("\nExplicit PII only:")
    result = await router.check(text, dimensions=["pii_detection"])
    print(f"  Dimensions: {result.routing_info['dimensions_requested']}")
    print(f"  Safe: {result.safe}")

    # Explicit - check multiple specific dimensions
    print("\nExplicit PII + toxicity + copyright:")
    result = await router.check(text, dimensions=["pii_detection", "toxicity", "copyright"])
    print(f"  Models dispatched: {result.routing_info['models_dispatched']}")
    print(f"  Results:")
    for dr in result.dimension_results:
        print(f"    {dr.dimension}: safe={dr.safe} (via {dr.model_name})")

    await router.close()


if __name__ == "__main__":
    asyncio.run(main())
