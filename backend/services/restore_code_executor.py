import base64 as base64_module
import datetime as datetime_module
import hashlib as hashlib_module
import math as math_module
import random as random_module
import re
import string as string_module
import time as time_module
import uuid as uuid_module
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

import logging

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="restore_anon_")


class CodeExecutionError(Exception):
    """Raised when sandboxed code execution fails."""


class RestoreCodeExecutor:
    """Sandboxed execution helpers for generated anonymization code."""

    def safe_execute_simple(self, code: str, text: str) -> str:
        safe_globals = {
            "__builtins__": {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "ord": ord,
                "chr": chr,
                "isinstance": isinstance,
                "sorted": sorted,
                "reversed": reversed,
                "map": map,
                "filter": filter,
                "hex": hex,
                "bin": bin,
                "oct": oct,
                "round": round,
                "pow": pow,
                "divmod": divmod,
                "any": any,
                "all": all,
                "repr": repr,
                "hash": hash,
                "set": set,
                "frozenset": frozenset,
                "bytes": bytes,
                "bytearray": bytearray,
                "slice": slice,
                "type": type,
            },
            "re": re,
            "string": string_module,
            "random": random_module,
            "hashlib": hashlib_module,
            "time": time_module,
            "datetime": datetime_module,
            "base64": base64_module,
            "uuid": uuid_module,
            "math": math_module,
        }
        safe_locals = {}

        try:
            exec(code, safe_globals, safe_locals)
            if "anonymize" not in safe_locals:
                raise CodeExecutionError("Code must define an 'anonymize' function")

            anonymize_func = safe_locals["anonymize"]
            result = anonymize_func(text)
            if not isinstance(result, str):
                result = str(result)
            return result
        except Exception as exc:
            raise CodeExecutionError(f"Execution error: {str(exc)}")

    def safe_execute(
        self,
        code: str,
        input_text: str,
        entity_type_code: str,
        existing_mapping: Dict[str, str],
        existing_counters: Dict[str, int],
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        counter_key = entity_type_code.lower()
        initial_counter = existing_counters.get(counter_key, 0)
        state = {"counter": initial_counter, "mapping": {}}
        result = {
            "anonymized_text": input_text,
            "mapping": {},
            "counters": existing_counters.copy(),
        }

        safe_globals = {
            "__builtins__": {
                "len": len,
                "str": str,
                "int": int,
                "dict": dict,
                "list": list,
                "range": range,
                "enumerate": enumerate,
                "min": min,
                "max": max,
                "sorted": sorted,
                "reversed": reversed,
                "zip": zip,
                "map": map,
                "filter": filter,
                "any": any,
                "all": all,
                "True": True,
                "False": False,
                "None": None,
            },
            "re": re,
            "input_text": input_text,
            "entity_type_code": entity_type_code,
            "existing_mapping": existing_mapping.copy(),
            "existing_counters": existing_counters.copy(),
            "state": state,
            "result": result,
        }
        safe_locals = {}

        def execute_code():
            try:
                exec(code, safe_globals, safe_locals)
                exec_result = safe_globals["result"]

                if not exec_result.get("mapping") and safe_globals.get("state", {}).get("mapping"):
                    exec_result["mapping"] = safe_globals["state"]["mapping"]
                    logger.debug(
                        f"Recovered mapping from safe_globals['state']: {exec_result['mapping']}"
                    )

                state_counter = safe_globals.get("state", {}).get("counter", 0)
                if state_counter > 0:
                    recovered_counter_key = safe_globals.get("entity_type_code", "").lower()
                    if recovered_counter_key:
                        exec_result["counters"] = safe_globals.get("existing_counters", {}).copy()
                        exec_result["counters"][recovered_counter_key] = state_counter
                        logger.debug(
                            "Recovered counter from safe_globals['state']: "
                            f"{recovered_counter_key}={state_counter}"
                        )

                return exec_result
            except Exception as exc:
                raise CodeExecutionError(f"Code execution failed: {str(exc)}")

        try:
            future = _executor.submit(execute_code)
            return future.result(timeout=timeout)
        except TimeoutError:
            raise CodeExecutionError(f"Code execution timed out after {timeout} seconds")
        except Exception as exc:
            if isinstance(exc, CodeExecutionError):
                raise
            raise CodeExecutionError(f"Code execution error: {str(exc)}")
