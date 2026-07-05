from typing import Dict, List

from config import settings
from services.risk_policy import highest_risk_level
from utils.logger import setup_logger
from utils.scanner_cache import get_compiled_regex, get_keyword_assets

logger = setup_logger()


class ScannerPatternExecutor:
    """Executes regex and keyword scanners plus final aggregation."""

    def execute_regex_scanners(
        self,
        scanners: List[Dict],
        content: str,
        result_cls,
    ) -> List:
        logger.info(f"Executing {len(scanners)} Regex scanners")
        results = []
        max_samples = settings.scanner_match_sample_limit
        max_count = settings.scanner_regex_match_count_limit

        for scanner in scanners:
            tag = scanner["tag"]
            name = scanner["name"]
            pattern = scanner["definition"]
            risk_level = scanner["risk_level"]

            try:
                regex = get_compiled_regex(pattern)
                if regex is None:
                    raise ValueError("Invalid regex pattern")

                match_samples = []
                match_count = 0
                truncated = False
                for match in regex.finditer(content):
                    match_count += 1
                    if len(match_samples) < max_samples:
                        match_samples.append(match.group(0))
                    if match_count >= max_count:
                        truncated = True
                        break

                matched = match_count > 0
                match_details = None
                if matched:
                    count_display = f">={max_count}" if truncated else str(match_count)
                    match_details = f"Matched {count_display} times. Samples: {match_samples}"
                    logger.info(f"Regex scanner {tag} matched: {match_details}")

                results.append(
                    result_cls(
                        scanner_tag=tag,
                        scanner_name=name,
                        scanner_type="regex",
                        risk_level=risk_level,
                        matched=matched,
                        match_details=match_details,
                    )
                )
            except ValueError as exc:
                logger.error(f"Invalid regex pattern for scanner {tag}: {exc}")
                results.append(
                    result_cls(
                        scanner_tag=tag,
                        scanner_name=name,
                        scanner_type="regex",
                        risk_level=risk_level,
                        matched=False,
                        match_details=f"Error: Invalid regex pattern - {str(exc)}",
                    )
                )
            except Exception as exc:
                logger.error(f"Error executing regex scanner {tag}: {exc}")
                results.append(
                    result_cls(
                        scanner_tag=tag,
                        scanner_name=name,
                        scanner_type="regex",
                        risk_level=risk_level,
                        matched=False,
                    )
                )

        return results

    def execute_keyword_scanners(
        self,
        scanners: List[Dict],
        content: str,
        result_cls,
    ) -> List:
        logger.info(f"Executing {len(scanners)} Keyword scanners")
        normalized_content = content.casefold()
        results = []
        max_samples = settings.scanner_match_sample_limit

        for scanner in scanners:
            tag = scanner["tag"]
            name = scanner["name"]
            keywords_str = scanner["definition"]
            risk_level = scanner["risk_level"]

            try:
                keywords, keyword_regex = get_keyword_assets(keywords_str)
                if not keywords:
                    logger.warning(f"Keyword scanner {tag} has no valid keywords")
                    results.append(
                        result_cls(
                            scanner_tag=tag,
                            scanner_name=name,
                            scanner_type="keyword",
                            risk_level=risk_level,
                            matched=False,
                            match_details="No valid keywords defined",
                        )
                    )
                    continue

                matched_keywords = set()
                if keyword_regex:
                    for match in keyword_regex.finditer(content):
                        matched_keywords.add(match.group(0).casefold())
                        if len(matched_keywords) >= max_samples:
                            break
                else:
                    for keyword in keywords:
                        if keyword in normalized_content:
                            matched_keywords.add(keyword)
                            if len(matched_keywords) >= max_samples:
                                break

                matched = len(matched_keywords) > 0
                match_details = None
                if matched:
                    match_samples = sorted(matched_keywords)[:max_samples]
                    match_details = f"Matched keywords: {match_samples}"
                    logger.info(f"Keyword scanner {tag} matched: {match_details}")

                results.append(
                    result_cls(
                        scanner_tag=tag,
                        scanner_name=name,
                        scanner_type="keyword",
                        risk_level=risk_level,
                        matched=matched,
                        match_details=match_details,
                    )
                )
            except Exception as exc:
                logger.error(f"Error executing keyword scanner {tag}: {exc}")
                results.append(
                    result_cls(
                        scanner_tag=tag,
                        scanner_name=name,
                        scanner_type="keyword",
                        risk_level=risk_level,
                        matched=False,
                    )
                )

        return results

    def aggregate_results(self, scanner_results: List, aggregate_cls):
        matched_scanners = [result for result in scanner_results if result.matched]
        if not matched_scanners:
            logger.info("No scanners matched - content is safe")
            return aggregate_cls(
                overall_risk_level="no_risk",
                matched_scanners=[],
                compliance_categories=[],
                security_categories=[],
            )

        logger.info(f"{len(matched_scanners)} scanners matched")
        overall_risk_level = highest_risk_level(
            scanner.risk_level for scanner in matched_scanners
        )

        security_categories = []
        compliance_categories = []
        for scanner in matched_scanners:
            if scanner.scanner_tag == "S9":
                security_categories.append(scanner.scanner_name)
            else:
                compliance_categories.append(scanner.scanner_name)

        logger.info(
            f"Overall risk: {overall_risk_level}, Compliance: {len(compliance_categories)}, Security: {len(security_categories)}"
        )
        return aggregate_cls(
            overall_risk_level=overall_risk_level,
            matched_scanners=matched_scanners,
            compliance_categories=compliance_categories,
            security_categories=security_categories,
        )
