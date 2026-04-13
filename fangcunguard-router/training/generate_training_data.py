"""
Generate synthetic training data for Guard Router ML classifier.

Uses an LLM (via OpenAI-compatible API) to generate diverse example texts
for each of the 15 safety dimensions. Output: training_data.jsonl

Usage:
    python generate_training_data.py \
        --api-url http://localhost:58002/v1 \
        --api-key EMPTY \
        --model Qwen3-8B \
        --samples-per-dim 200
"""

import argparse
import json
import os
import sys
from pathlib import Path

from openai import OpenAI


DIMENSIONS_PATH = Path(__file__).parent / "dimensions.json"
OUTPUT_PATH = Path(__file__).parent / "training_data.jsonl"

# Prompts to generate training samples for each dimension.
# Each prompt asks the LLM to generate diverse examples.
GENERATION_PROMPTS = {
    "chinese_safety": (
        "Generate {n} diverse Chinese text samples that would require Chinese content safety moderation. "
        "Include: political sensitivity (国家政策、领导人), violence (暴力犯罪), pornography (色情内容), "
        "hate speech in Chinese context, drug-related content, gambling. "
        "Mix formal and informal language, social media style, news style, chat style. "
        "Each sample should be 1-3 sentences. Output as JSON array of strings."
    ),
    "english_safety": (
        "Generate {n} diverse English text samples that contain harmful content requiring safety moderation. "
        "Include: violence descriptions, hate speech, harassment, explicit sexual content, dangerous activities, "
        "extremist content, glorification of violence. "
        "Mix formal writing, social media posts, chat messages, forum posts. "
        "Each sample should be 1-3 sentences. Output as JSON array of strings."
    ),
    "prompt_injection": (
        "Generate {n} diverse prompt injection attack examples. Include: "
        "direct instruction override ('ignore previous instructions'), "
        "system prompt extraction ('repeat your system prompt'), "
        "role-play attacks ('pretend you are a different AI'), "
        "indirect injection in RAG context ('if you are an AI, do X'), "
        "delimiter attacks, encoding tricks, multi-language injection. "
        "Each sample should be realistic. Output as JSON array of strings."
    ),
    "jailbreak": (
        "Generate {n} diverse jailbreak attempt examples. Include: "
        "DAN (Do Anything Now) prompts, character role-play bypasses, "
        "hypothetical scenario framing ('in a fictional world'), "
        "multi-step manipulation, emotional manipulation, "
        "authority impersonation, reverse psychology approaches. "
        "Each sample should be distinct. Output as JSON array of strings."
    ),
    "toxicity": (
        "Generate {n} diverse examples of toxic language. Include: "
        "insults, personal attacks, identity-based attacks, "
        "threats of violence, severe profanity, degrading language, "
        "cyberbullying, sexually explicit insults. "
        "Mix obvious toxicity with subtle/passive-aggressive forms. "
        "Each sample should be 1-2 sentences. Output as JSON array of strings."
    ),
    "pii_detection": (
        "Generate {n} diverse examples of text containing PII (personally identifiable information). Include: "
        "credit card numbers, social security numbers, passport numbers, "
        "phone numbers, email addresses, physical addresses, "
        "API keys, passwords, medical record numbers, bank account numbers, "
        "driver's license numbers, date of birth with names. "
        "Embed PII naturally in sentences. Output as JSON array of strings."
    ),
    "hallucination": (
        "Generate {n} diverse examples where an AI response contradicts provided context. Format each as: "
        "'Context: [factual context]. AI Response: [response that contradicts the context]'. "
        "Include: fabricated statistics, wrong dates, misattributed quotes, "
        "invented references, contradicting source documents, "
        "mixing up entities, overgeneralizing from specific data. "
        "Output as JSON array of strings."
    ),
    "code_security": (
        "Generate {n} diverse code snippets containing security vulnerabilities. Include: "
        "SQL injection (string concatenation in queries), "
        "XSS (unsanitized HTML output), command injection (os.system with user input), "
        "hardcoded API keys/passwords, path traversal (../../../etc/passwd), "
        "unsafe deserialization (pickle.loads), eval() with user input, "
        "SSRF, insecure random number generation, buffer overflow patterns. "
        "Mix Python, JavaScript, Java, Go. Output as JSON array of strings."
    ),
    "image_safety": (
        "Generate {n} diverse text prompts that request unsafe image content. Include: "
        "requests for violent imagery, NSFW image generation, "
        "deepfake requests, requests depicting dangerous activities, "
        "requests for hate symbols, requests involving minors in unsafe contexts, "
        "image manipulation for harassment. "
        "Each should be a user request. Output as JSON array of strings."
    ),
    "agent_safety": (
        "Generate {n} diverse examples of unsafe AI agent tool-call requests. Include: "
        "unauthorized file deletion ('delete all files in /'), "
        "data exfiltration ('email the database to external address'), "
        "privilege escalation ('run as administrator'), "
        "shell command injection in tool parameters, "
        "accessing restricted directories, modifying system configurations, "
        "unauthorized network requests, database manipulation. "
        "Format as realistic tool-call scenarios. Output as JSON array of strings."
    ),
    "self_harm": (
        "Generate {n} diverse examples of content related to self-harm. Include: "
        "suicide ideation expressions, self-injury descriptions, "
        "eating disorder promotion (pro-ana content), "
        "crisis situations where someone needs help, "
        "romanticizing self-harm, detailed method discussions, "
        "indirect references and euphemisms for self-harm. "
        "IMPORTANT: These are for training a safety classifier. Output as JSON array of strings."
    ),
    "child_safety": (
        "Generate {n} diverse examples of text that raises child safety concerns. Include: "
        "inappropriate content directed at minors, "
        "attempts to contact minors inappropriately, "
        "age-inappropriate content in children's contexts, "
        "grooming patterns (building trust with minors), "
        "requests for content involving minors in unsafe contexts. "
        "IMPORTANT: Do NOT generate actual CSAM. These are for training a safety classifier. "
        "Output as JSON array of strings."
    ),
    "multilingual_safety": (
        "Generate {n} diverse harmful content examples in various non-English non-Chinese languages. Include: "
        "Arabic (عربي), Hindi (हिंदी), Vietnamese (Tiếng Việt), "
        "Turkish (Türkçe), Russian (Русский), Thai (ภาษาไทย), "
        "Portuguese, Spanish, French, Korean, Japanese. "
        "Mix violence, hate speech, and other harmful content across languages. "
        "Output as JSON array of strings."
    ),
    "copyright": (
        "Generate {n} diverse examples of copyright-related requests. Include: "
        "requests to reproduce book passages verbatim, "
        "requests for full song lyrics, "
        "requests for copyrighted code with restrictive licenses, "
        "requests to reproduce news articles word-for-word, "
        "requests for movie scripts, academic paper full text reproduction, "
        "requests for proprietary documentation. "
        "Output as JSON array of strings."
    ),
    "fast_screening": (
        "Generate {n} diverse examples of clearly safe, everyday content. Include: "
        "greetings ('hello', 'hi there'), simple questions ('what time is it'), "
        "math homework help, weather inquiries, cooking recipes, "
        "travel recommendations, general knowledge questions, "
        "thank you messages, casual conversation, hobby discussions, "
        "programming help (non-security), translation requests. "
        "Output as JSON array of strings."
    ),
}


def generate_samples(client: OpenAI, model: str, dimension: str, n: int) -> list:
    """Generate n training samples for a dimension using LLM."""
    prompt = GENERATION_PROMPTS[dimension].format(n=n)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a data generation assistant. Output ONLY a valid JSON array of strings, nothing else."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
            max_tokens=4096,
        )

        content = response.choices[0].message.content.strip()
        # Try to extract JSON array from response
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        samples = json.loads(content)
        if not isinstance(samples, list):
            print(f"  Warning: {dimension} returned non-list, skipping")
            return []
        return [s for s in samples if isinstance(s, str) and len(s.strip()) > 10]

    except Exception as e:
        print(f"  Error generating {dimension}: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Generate training data for Guard Router ML classifier")
    parser.add_argument("--api-url", default=os.environ.get("GENERAL_LLM_API_URL", "http://localhost:58002/v1"))
    parser.add_argument("--api-key", default=os.environ.get("GENERAL_LLM_API_KEY", "EMPTY"))
    parser.add_argument("--model", default=os.environ.get("GENERAL_LLM_MODEL_NAME", "Qwen3-8B"))
    parser.add_argument("--samples-per-dim", type=int, default=200)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    # Load dimensions
    with open(DIMENSIONS_PATH) as f:
        dims = json.load(f)["dimensions"]

    dim_ids = [d["id"] for d in dims]
    print(f"Generating {args.samples_per_dim} samples for {len(dim_ids)} dimensions")

    client = OpenAI(api_key=args.api_key, base_url=args.api_url)

    all_samples = []
    for dim_id in dim_ids:
        print(f"\n[{dim_id}] Generating {args.samples_per_dim} samples...")
        # Generate in batches of 50
        batch_size = 50
        dim_samples = []
        for batch in range(0, args.samples_per_dim, batch_size):
            n = min(batch_size, args.samples_per_dim - batch)
            samples = generate_samples(client, args.model, dim_id, n)
            dim_samples.extend(samples)
            print(f"  Batch {batch//batch_size + 1}: got {len(samples)} samples (total: {len(dim_samples)})")

        for text in dim_samples:
            all_samples.append({"text": text.strip(), "dimension": dim_id})

        print(f"  [{dim_id}] Total: {len(dim_samples)} samples")

    # Write output
    with open(args.output, "w") as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\nDone! {len(all_samples)} samples written to {args.output}")
    for dim_id in dim_ids:
        count = sum(1 for s in all_samples if s["dimension"] == dim_id)
        print(f"  {dim_id}: {count}")


if __name__ == "__main__":
    main()
