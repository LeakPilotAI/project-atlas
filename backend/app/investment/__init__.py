"""ATLAS Investment Intelligence Engine — Phase 1–5.1 + collection monitor.

Completely independent from the Hyperliquid trading / paper engine.
Collection/readiness layer: dataset trust only. No real brokerage. No ML.
"""



__all__ = [
    "AssetType",
    "DataQuality",
    "EvidenceQuality",
    "InvestmentAlertState",
    "InvestmentHorizon",
    "RiskTolerance",
    "ThesisState",
    "FreshnessRules",
    "classify_freshness",
    "AllocationPlan",
    "AllocationTier",
    "HoldingInput",
    "InvestmentAsset",
    "InvestmentOpportunity",
    "InvestmentSnapshot",
    "MeasuredValue",
    "PaperInvestmentAccount",
    "PortfolioInput",
    "NullProvider",
    "InvestmentResearch",
    "ResearchRecord",
    "SCORING_VERSION",
    "format_research_text",
    "SAFETY_RULES",
    "DATA_DIR",
    "LEDGER_PATH",
    "InvestmentUniverse",
    "load_universe",
    "YahooPriceProvider",
    "YahooFundamentalProvider",
    "YahooValuationProvider",
]

from importlib import import_module as _import_module

_LAZY_EXPORTS = {'AllocationPlan': ('app.investment.models', 'AllocationPlan'), 'AllocationTier': ('app.investment.models', 'AllocationTier'), 'AssetType': ('app.investment.enums', 'AssetType'), 'DATA_DIR': ('app.investment.storage', 'DATA_DIR'), 'DataQuality': ('app.investment.enums', 'DataQuality'), 'EvidenceQuality': ('app.investment.enums', 'EvidenceQuality'), 'FreshnessRules': ('app.investment.freshness', 'FreshnessRules'), 'HoldingInput': ('app.investment.models', 'HoldingInput'), 'InvestmentAlertState': ('app.investment.enums', 'InvestmentAlertState'), 'InvestmentAsset': ('app.investment.models', 'InvestmentAsset'), 'InvestmentHorizon': ('app.investment.enums', 'InvestmentHorizon'), 'InvestmentOpportunity': ('app.investment.models', 'InvestmentOpportunity'), 'InvestmentResearch': ('app.investment.research', 'InvestmentResearch'), 'InvestmentSnapshot': ('app.investment.snapshot', 'InvestmentSnapshot'), 'InvestmentUniverse': ('app.investment.universe', 'InvestmentUniverse'), 'LEDGER_PATH': ('app.investment.storage', 'LEDGER_PATH'), 'MeasuredValue': ('app.investment.models', 'MeasuredValue'), 'NullProvider': ('app.investment.providers', 'NullProvider'), 'PaperInvestmentAccount': ('app.investment.models', 'PaperInvestmentAccount'), 'PortfolioInput': ('app.investment.models', 'PortfolioInput'), 'ResearchRecord': ('app.investment.research_models', 'ResearchRecord'), 'RiskTolerance': ('app.investment.enums', 'RiskTolerance'), 'SAFETY_RULES': ('app.investment.safety', 'SAFETY_RULES'), 'SCORING_VERSION': ('app.investment.research_models', 'SCORING_VERSION'), 'ThesisState': ('app.investment.enums', 'ThesisState'), 'YahooFundamentalProvider': ('app.investment.yahoo_fundamentals', 'YahooFundamentalProvider'), 'YahooPriceProvider': ('app.investment.yahoo_price', 'YahooPriceProvider'), 'YahooValuationProvider': ('app.investment.yahoo_fundamentals', 'YahooValuationProvider'), 'classify_freshness': ('app.investment.freshness', 'classify_freshness'), 'format_research_text': ('app.investment.research', 'format_research_text'), 'load_universe': ('app.investment.universe', 'load_universe')}

def __getattr__(name):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    module_name, symbol = _LAZY_EXPORTS[name]
    value = getattr(_import_module(module_name), symbol)
    globals()[name] = value
    return value

def __dir__():
    return sorted(set(globals()) | set(__all__))
