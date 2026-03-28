"""
JARVIS v2 — context_injector.py (Phase B)

Upgraded:
- Action enforcement (skills DO things, don't ask)
- Better workflow step handoff
- Concise system prompts to save tokens
- Step-aware context for workflows
"""
from pathlib import Path


MODE_PROMPTS = {
    "concise": (
        "\n\nMODE: CONCISE"
        "\n- Max 3-5 sentences. Bullets. No fluff."
    ),
    "detailed": (
        "\n\nMODE: DETAILED"
        "\n- Thorough explanations with examples."
        "\n- Break down complex topics."
    ),
    "creative": (
        "\n\nMODE: CREATIVE"
        "\n- Think outside the box. Bold ideas."
    ),
    "act": (
        "\n\nMODE: ACTION — CRITICAL RULES:"
        "\n- NEVER ask the user for more information"
        "\n- NEVER say 'please provide' or 'I need'"
        "\n- NEVER ask 'would you like to' or 'shall I'"
        "\n- Make reasonable assumptions and EXECUTE"
        "\n- If target unknown, use example.com as demo"
        "\n- Show actual output: code, commands, results, analysis"
        "\n- You are the expert — DECIDE and DELIVER"
        "\n- Every response must contain actionable content"
    ),
    "minimal": (
        "\n\nMODE: MINIMAL"
        "\n- One line max. Code only. No explanation."
    ),
}

# Workflow step instructions — makes each step produce unique output
STEP_PROMPTS = {
    "Methodology": "Outline the specific methodology and approach. List exact steps you will take.",
    "Scan": "Execute the scan. Show specific findings with severity ratings. List CVEs if applicable.",
    "Web layer": "Test web-specific vulnerabilities: XSS, CSRF, SSRF, open redirects. Show payloads tested and results.",
    "API security": "Test API endpoints: auth bypass, IDOR, rate limiting, injection. Show request/response examples.",
    "Privilege escalation": "Check for privesc vectors: SUID, cron, kernel, misconfigs. Show commands and output.",
    "Final report": "Write the final security report with: Executive Summary, Findings (sorted by severity), Remediation steps, Risk ratings.",
    "Ideation": "Generate 5 concrete ideas with market size estimates and unique value propositions.",
    "Plan": "Create a detailed project plan with milestones, tech stack decisions, and timeline.",
    "Architecture": "Design the system architecture. Show components, data flow, and API structure.",
    "Frontend": "Write the key frontend components. Show actual code for the main views.",
    "API": "Design and implement the API endpoints. Show route definitions and handler code.",
    "Tests": "Write actual test cases. Show test code for critical paths.",
    "PR": "Format as a pull request: title, description, changes summary, testing done.",
    "Diagnose": "Analyze the error systematically. Check logs, stack traces, recent changes.",
    "Strategy": "Propose 2-3 fix strategies ranked by likelihood of success.",
    "Validate": "Verify the fix works. Show test commands and expected vs actual output.",
    "Submit fix": "Format as a clean commit: message, diff summary, tests passing.",
    "Containerise": "Write the Dockerfile and docker-compose.yml. Show actual file contents.",
    "AWS setup": "Define the infrastructure. Show CloudFormation/Terraform or CLI commands.",
    "Deploy": "Execute deployment steps. Show commands and verify endpoints.",
    "Monitor": "Set up monitoring and alerting. Show config for logging, metrics, health checks.",
    "RAG setup": "Design the RAG pipeline: embeddings, vector store, retrieval chain. Show code.",
    "Agent graph": "Design the agent graph: nodes, edges, state management. Show LangGraph code.",
    "Prompts": "Write the system prompts for each agent node. Show actual prompt text.",
    "Design": "Create the system design. Show architecture diagram (ASCII), components, interfaces.",
}


def build_messages(
    query: str,
    memory,
    persona: str,
    skill: dict = None,
    settings=None,
    mode: str = None,
    workflow_step: str = None,
    step_number: int = None,
    total_steps: int = None,
) -> list:
    """
    Build messages[] for brain.stream().
    Now with action enforcement and workflow step awareness.
    """
    # 1. Recalled past tasks
    recalled = memory.recall(query)

    # 2. Active pins
    pins_text = memory.get_pins_text()

    # 3. Conversation mode
    mode = mode or memory.kv_get("mode", "act")
    mode_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["act"])

    # 4. Skill instructions
    skill_instructions = ""
    if skill and settings:
        skill_md = settings.SKILLS_DIR / skill["name"] / "SKILL.md"
        if Path(skill_md).exists():
            content = Path(skill_md).read_text(errors="ignore")
            skill_instructions = content[:3000]

    # 5. Workflow step context
    step_context = ""
    if workflow_step:
        step_prompt = STEP_PROMPTS.get(workflow_step, "")
        if step_prompt:
            step_context = (
                f"\n\n== WORKFLOW STEP {step_number}/{total_steps}: {workflow_step} =="
                f"\n{step_prompt}"
                f"\n\nCRITICAL: You are executing step {step_number} of {total_steps}."
                f"\nDo NOT repeat previous steps. Do NOT ask for information."
                f"\nProduce UNIQUE output for THIS step only."
                f"\nBe specific and actionable. Show real results."
            )

    # 6. Build system prompt
    parts = [persona.strip()]
    parts.append(mode_prompt)

    if step_context:
        parts.append(step_context)

    if pins_text:
        parts.append(f"\n== Context ==\n{pins_text}")

    if recalled and not workflow_step:  # Skip recall in workflow steps to save tokens
        parts.append(f"\n== Memory ==\n{recalled}")

    if skill_instructions:
        parts.append(
            f"\n== Skill: {skill['name']} ==\n{skill_instructions}"
        )

    system = "\n\n".join(p for p in parts if p.strip())

    # 7. Assemble messages
    messages = [{"role": "system", "content": system}]

    # Only add history for non-workflow queries (saves tokens)
    if not workflow_step:
        messages.extend(memory.short_term())

    messages.append({"role": "user", "content": query})

    return messages
