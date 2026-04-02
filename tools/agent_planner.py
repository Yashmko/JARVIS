class AgentPlanner:
    def plan(self, query):
        q = query.lower()

        if "scan" in q or "recon" in q:
            return ["subfinder", "httpx", "nmap", "nuclei"]

        if "find" in q and "api" in q:
            return ["subfinder", "httpx", "grep"]

        if "security" in q:
            return ["subfinder", "headers", "nmap", "nuclei"]

        return ["llm"]
