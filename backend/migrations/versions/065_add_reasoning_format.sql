-- Add reasoning_format column to upstream_api_configs
-- Allows per-model configuration of how reasoning content is extracted:
--   auto: try reasoning_content field first, then <think> tags (default, backward compatible)
--   field: only extract from reasoning_content field (OpenAI o1/o3, DeepSeek-R1)
--   tag: only extract from <think> tags in content (MiniMax M2.5, QwQ)
--   none: skip reasoning extraction entirely (GPT-4o, Claude, normal chat models)

ALTER TABLE upstream_api_configs
ADD COLUMN IF NOT EXISTS reasoning_format VARCHAR(20) DEFAULT 'auto';
