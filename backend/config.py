from typing import Optional  # fcg-rewrite
from pydantic_settings import BaseSettings  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

def get_version() -> str:  # fcg-rewrite
    """
    Get version number, priority:
    1. VERSION file
    2. Environment variable APP_VERSION
    3. Default version
    """
    try:
        # Try to read from VERSION file
        version_file = Path(__file__).parent.parent / "VERSION"  # fcg-rewrite
        if version_file.exists():  # fcg-rewrite
            return version_file.read_text().strip()  # fcg-rewrite
    except Exception:  # fcg-rewrite
        pass
    
    # Try to get from environment variable
    import os  # fcg-rewrite
    env_version = os.getenv('APP_VERSION')  # fcg-rewrite
    if env_version:  # fcg-rewrite
        return env_version  # fcg-rewrite
    
    # Default version
    return "1.0.0"  # fcg-rewrite

class Settings(BaseSettings):  # fcg-rewrite
    # Application configuration
    app_name: str = "FangcunGuard"  # fcg-rewrite
    app_version: str = get_version()  # fcg-rewrite
    debug: bool = False  # fcg-rewrite
    
    # Super admin configuration
    # Warning: Please modify these default values in production environment!
    super_admin_username: str = "admin@yourdomain.com"  # fcg-rewrite
    super_admin_password: str = "CHANGE-THIS-PASSWORD-IN-PRODUCTION"  # fcg-rewrite
    
    # Data directory configuration
    data_dir: str = "/mnt/data/fangcunguard-data"  # fcg-rewrite

    @property  # fcg-rewrite
    def media_dir(self) -> str:  # fcg-rewrite
        """Media file directory"""
        return f"{self.data_dir}/media"  # fcg-rewrite
    
    # Database configuration
    database_url: str = "postgresql://fangcunguard:your_password@localhost:54321/fangcunguard"  # fcg-rewrite
    
    # Model configuration
    guardrails_model_api_url: str = "http://your-host-ip:your-port/v1"  # fcg-rewrite
    guardrails_model_api_key: str = "your-guardrails-model-api-key"  # fcg-rewrite
    guardrails_model_name: str = "Qwen3Guard-Gen-8B"  # fcg-rewrite

    # General-purpose LLM configuration (for text generation tasks: anonymization, regex generation, appeal review, etc.)
    general_llm_api_url: str = "http://your-host-ip:your-port/v1"  # fcg-rewrite
    general_llm_api_key: str = "your-general-llm-api-key"  # fcg-rewrite
    general_llm_model_name: str = "Qwen/Qwen3-8B"  # fcg-rewrite

    # Multimodal model configuration
    guardrails_vl_model_api_url: str = "http://localhost:58003/v1"  # fcg-rewrite
    guardrails_vl_model_api_key: str = "your-vl-model-api-key"  # fcg-rewrite
    guardrails_vl_model_name: str = "Qwen3Guard-VL"  # fcg-rewrite
    
    # Detection maximum context length configuration (should be equal to model max-model-len - 1000)
    max_detection_context_length: int = 7168  # fcg-rewrite

    # Prompt Guard server URL (Prompt Injection detection)
    prompt_guard_url: str = "http://127.0.0.1:58006"  # fcg-rewrite

    # Guard Model Router configuration
    # Path to guard_models.yaml (relative to backend/ or absolute). Empty = disabled.
    guard_models_config_path: str = ""  # fcg-rewrite

    # Scanner performance tuning
    scanner_regex_cache_size: int = 1024  # fcg-rewrite
    scanner_keyword_cache_size: int = 1024  # fcg-rewrite
    scanner_keyword_regex_threshold: int = 8  # fcg-rewrite
    scanner_match_sample_limit: int = 5  # fcg-rewrite
    scanner_regex_match_count_limit: int = 200  # fcg-rewrite
    scanner_window_max_windows: int = 12  # fcg-rewrite
    scanner_window_max_pairs: int = 64  # fcg-rewrite
    scanner_window_concurrency: int = 8  # fcg-rewrite
    
    # Embedding model API configuration
    # Used for knowledge base vectorization
    embedding_api_base_url: str = "http://your-host-ip:your-port/v1"  # fcg-rewrite
    embedding_api_key: str = "your-embedding-api-key"  # fcg-rewrite
    embedding_model_name: str = "FangcunGuard-Embedding-1024"  # fcg-rewrite
    embedding_model_dimension: int = 1024  # Embedding vector dimension  # fcg-rewrite
    embedding_similarity_threshold: float = 0.7  # Default similarity threshold (fallback when KB-specific threshold is not available)  # fcg-rewrite
    embedding_max_results: int = 5  # Maximum return results  # fcg-rewrite

    # API configuration
    cors_origins: str = "*"  # fcg-rewrite
    
    # Log configuration  
    log_level: str = "INFO"  # fcg-rewrite
    
    @property  # fcg-rewrite
    def log_dir(self) -> str:  # fcg-rewrite
        """Log directory"""
        return f"{self.data_dir}/logs"  # fcg-rewrite
    
    @property   # fcg-rewrite
    def detection_log_dir(self) -> str:  # fcg-rewrite
        """Detection result log directory"""
        return f"{self.data_dir}/logs/detection"  # fcg-rewrite
    
    # Contact information
    support_email: str = "support@yourdomain.com"  # fcg-rewrite
    
    # HuggingFace model
    huggingface_model: str = "Qwen/Qwen3Guard-Gen-8B"  # fcg-rewrite
    
    # JWT configuration
    # Warning: Please generate a secure random key! Use: openssl rand -base64 64
    jwt_secret_key: str = "GENERATE-A-SECURE-RANDOM-JWT-KEY-IN-PRODUCTION"  # fcg-rewrite
    jwt_algorithm: str = "HS256"  # fcg-rewrite
    jwt_access_token_expire_minutes: int = 1440  # fcg-rewrite
    
    # Email configuration
    smtp_server: str = ""  # fcg-rewrite
    smtp_port: Optional[int] = None  # fcg-rewrite
    smtp_username: str = ""  # fcg-rewrite
    smtp_password: str = ""  # fcg-rewrite
    smtp_use_tls: Optional[bool] = None  # fcg-rewrite
    smtp_use_ssl: Optional[bool] = None  # fcg-rewrite
    
    # Frontend URL configuration
    frontend_url: str = "https://fangcunguard.com"  # fcg-rewrite

    # Server configuration - dual service architecture
    host: str = "0.0.0.0"  # fcg-rewrite
    
    # Detection service host name (for inter-service calls)
    # Docker: detection-service, local: localhost
    detection_host: str = "localhost"  # fcg-rewrite
    
    # Management service configuration (low concurrency)
    admin_port: int = 5000  # fcg-rewrite
    admin_uvicorn_workers: int = 2  # fcg-rewrite
    admin_max_concurrent_requests: int = 50  # fcg-rewrite

    # Detection service configuration (high concurrency)
    detection_port: int = 5001  # fcg-rewrite
    detection_uvicorn_workers: int = 32  # fcg-rewrite
    detection_max_concurrent_requests: int = 400  # fcg-rewrite

    # Proxy service configuration (high concurrency)
    proxy_port: int = 5002  # fcg-rewrite
    proxy_uvicorn_workers: int = 24  # fcg-rewrite
    proxy_max_concurrent_requests: int = 300  # fcg-rewrite

    # Development and operations: whether to reset database (delete and rebuild all tables)
    reset_database_on_startup: bool = False  # fcg-rewrite

    # Private deployment configuration: whether to store detection results in the database
    # true: store to database (SaaS mode, complete data analysis)
    # false: only write log file (private mode, reduce database pressure)
    store_detection_results: bool = True  # fcg-rewrite

    # Default language configuration for private deployments without internet access
    # Options: 'en' (English) or 'zh' (Chinese)
    default_language: str = "en"  # fcg-rewrite

    # Deployment mode configuration
    # 'enterprise': Private enterprise deployment (default) - no subscription, no third-party package marketplace
    # 'saas': SaaS deployment - with subscription system and third-party package marketplace
    deployment_mode: str = "enterprise"  # fcg-rewrite

    # API domain configuration for documentation and examples
    # In SaaS mode: api.fangcunguard.com
    # In enterprise/private mode: http://localhost:5001 (or custom domain)
    api_domain: str = "https://api.fangcunguard.com" if deployment_mode.lower() == "saas" else "http://localhost:5001"  # fcg-rewrite


    @property  # fcg-rewrite
    def is_saas_mode(self) -> bool:  # fcg-rewrite
        """Check if running in SaaS mode"""
        return self.deployment_mode.lower() == "saas"  # fcg-rewrite

    @property  # fcg-rewrite
    def is_enterprise_mode(self) -> bool:  # fcg-rewrite
        """Check if running in enterprise mode (private deployment)"""
        return self.deployment_mode.lower() == "enterprise"  # fcg-rewrite

    # Default tenant limits
    # Default monthly scan limit for new tenants (detections per month)
    # Note: This should match free_user_monthly_quota for consistency
    # If not set, will use free_user_monthly_quota as default
    default_monthly_scan_limit: Optional[int] = None  # fcg-rewrite

    # Default rate limit for new tenants (requests per second)
    default_rate_limit_rps: int = 10  # fcg-rewrite

    # Payment configuration
    # Alipay configuration (used when default_language is 'zh')
    alipay_app_id: str = ""  # fcg-rewrite
    alipay_private_key: str = ""  # fcg-rewrite
    alipay_public_key: str = ""  # fcg-rewrite
    alipay_notify_url: str = ""  # e.g., https://yourdomain.com/api/v1/payment/webhook/alipay  # fcg-rewrite
    alipay_return_url: str = ""  # e.g., https://yourdomain.com/platform/billing/subscription  # fcg-rewrite
    alipay_gateway: str = "https://openapi.alipay.com/gateway.do"  # Production gateway  # fcg-rewrite
    # alipay_gateway: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"  # Sandbox gateway

    # Stripe configuration (used when default_language is not 'zh')
    stripe_secret_key: str = ""  # fcg-rewrite
    stripe_publishable_key: str = ""  # fcg-rewrite
    stripe_webhook_secret: str = ""  # fcg-rewrite
    stripe_price_id_monthly: str = ""  # Stripe Price ID for monthly subscription (legacy single-tier)  # fcg-rewrite
    stripe_price_ids: str = ""  # JSON mapping of tier_number to Stripe Price IDs, e.g. {"1":"price_xxx","2":"price_yyy"}  # fcg-rewrite
    stripe_subscription_success_url: str = ""  # e.g., http://localhost:3000/platform/subscription?payment=success&session_id={CHECKOUT_SESSION_ID}  # fcg-rewrite
    stripe_subscription_cancel_url: str = ""   # e.g., http://localhost:3000/platform/subscription?payment=cancelled  # fcg-rewrite
    stripe_package_success_url: str = ""       # e.g., http://localhost:3000/platform/config/scanner-packages?payment=success&session_id={CHECKOUT_SESSION_ID}  # fcg-rewrite
    stripe_package_cancel_url: str = ""        # e.g., http://localhost:3000/platform/config/scanner-packages?payment=cancelled  # fcg-rewrite

    # Subscription pricing
    subscription_price_cny: float = 19.0  # Monthly price in CNY  # fcg-rewrite
    subscription_price_usd: float = 19.0  # Monthly price in USD  # fcg-rewrite

    # Quota purchase pricing (pay-per-use for Chinese users via Alipay)
    quota_price_cny: float = 50.0  # Price per unit in CNY (¥50 per 10,000 calls)  # fcg-rewrite
    quota_calls_per_unit: int = 10000  # Number of API calls per purchase unit  # fcg-rewrite
    quota_validity_days: int = 365  # Purchased quota validity in days  # fcg-rewrite

    # Subscription quota limits
    free_user_monthly_quota: int = 1000  # Monthly quota for free users  # fcg-rewrite
    paid_user_monthly_quota: int = 100000  # Monthly quota for paid/subscribed users  # fcg-rewrite

    # VerifyMail.io API configuration for disposable email verification
    # If not configured, disposable email verification will be skipped
    verifymail_api_key: Optional[str] = None  # fcg-rewrite

    class Config:  # fcg-rewrite
        # Ensure we load the .env file next to this config module,
        # regardless of the current working directory
        env_file = str(Path(__file__).with_name('.env'))  # fcg-rewrite
        case_sensitive = False  # fcg-rewrite
        extra = "allow"  # fcg-rewrite

settings = Settings()  # fcg-rewrite
