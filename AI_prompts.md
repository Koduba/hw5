# HW5 — AI Prompts Log

## Problem 1: Vibe coder prompts

### Prompt 1

> lets work on homework 5, remember the rules?

### Prompt 2

> so the course pdf you have is for another course. but go ahead and create the prompts file

*What was lacking in Prompt 1:* it asked the agent to recall the rules but did not tell it to create the AI_prompts.md log for this homework.

### Prompt 3

> probmlem 1: vibecoder prompts
>
> creat a ai_prompt md file and log my insrucions for each problem. include problem numebr and title, my original prompt and folllow up prompt nd a note on ehat was lacking in the first. got it?

*What was lacking in Prompt 2:* it asked for the prompts file but did not say how to structure it: problem number and title, the original and follow-up prompts, and a note on what the first prompt was missing.

### Prompt 4

> Okay, so here is the scenario. We're gonna build a campus customs multi-agent operations. Which is an agentic team that runs the shop. Open tickets, land on a board, customer orders, rent, unpaid bills. Discount requests, whatever the shop has to handle. You will build three pieces that talk to each other. An MCP server, a fast API backend, with a multi-agent team. And a React dashboard, so a human can watch the agents at work and approve requests. Your agent team has full connectivity . Any agent may delegate tasks to any other agent for help . In this assignment, we are building these agents . One boss, who reads each ticket, decides who should work on it and makes final calls . Two inventory, checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock . Three accounting, watches cash and invoices, checks margins and prepares payments. All purchases, orders, for human approval. Four, facilities, handles the shop, space, side, lease, rent, etc. And five, customer service, who drafts messages for customers. We're gonna get data from a zip file, which has the data. Which is called data, so we're going to unzip so you can have data/campus_customs.db. That file is the original shop database. Tables include desk, tickets, inventory, pricing, vendors, leases, cash _accounts, payments, and invoices. Your tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db. And point your MCP server and backend at that working copy. Keep campus customs.db untouched. So we can reset when we want to restart resolving tickets. The rules of this shop. The field desk.date_today is today for the shop. Use this date to determine what is overdue. Vendor lead times come from the vendor's table. A vendor will not ship product while they still have an open unpaid invoice. Human approval is required for any payment. Points will be deducted if this is not done. So be careful. If payment is made, let's make sure to update the relevant table. If there is not enough cash, the pay tool must refuse . No negative balances . Cash only goes out in this homework . So we do not model revenue . So money no money comes in . Before a full run to resolve the tickets, let's make sure to reset the database to the original values . And do not email customers or call real vendors. Drafts stay on the board. So as you know, we're using portkey API key for all AI calls. So for this assignment, we're using only GPT-6 Luna like you have said. And through portkey for every agent, multi-agent tasks burn tokens fast. So do not use any other model in my code. Work 1 problem at a time. And I will be typing each problem in my own words. So let's get started.

*What was lacking in Prompt 3:* it set up the logging format but gave no project scenario, agent roles, or shop rules for the agent to work within.

### Prompt 5

> use only gpt 6 luna like i said

*What was lacking in Prompt 4:* it did not give the exact model ID, so the agent fell back to the workspace default (gpt-5.6-luna) instead of GPT-6 Luna.

## Problem 2: Study the Campus Customs database

### Prompt 1

> All right, problem two. Study the campus customs database. Now, we're gonna open the file data/campus_customs.db. And look through every table and each field. Copy the original file to data/campus_customs_new.db. Later problems update that working copy. Now study the three open tickets so you see how they link to other tables.

### Prompt 2

> Start output slash harness dot md. For each table, list the fields and one short line on why that table matters for the agents. You will keep growing this harness file in later problems.

*What was lacking in Prompt 1:* it asked the agent to study the database but did not ask for a lasting written reference of each table, its fields, and why it matters to the agents.

## Problem 3: Build the MCP server

### Prompt 1

> Problem 3, build the MCP server. Write an MCP server in MCP_server/ using fastmcp. It will talk to data/campus_customs_new.db. You do not need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. You will add more tools to it later. For now, write 3 tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data. Only use information in the database.

### Prompt 2

> In output/harness.MD, List each of your three MCP tools. For every tool, include which table it reads, which tickets it helps unlock, 101, 102, or 103, and one sentence on why that tool is the right one for that ticket. Vague lines like read inventory, score low, so tie the tool to the ticket. Also add a short mcp_server/readme.md file that explains what the MCP server is for, which database file it uses, and the three tools it has.

*What was lacking in Prompt 1:* it asked for the tools but not for documentation tying each tool to the tables it reads and to the specific tickets (101, 102, 103) it unlocks, or a README for the server.

## Problem 4: Add the MCP server to the vibe coder and test each tool

### Prompt 1

> Problem 4. Add the MCP server to Vibe Coder and test each tool. In your Vibe Coder, add your MCP server to this project so the Vibe Coder can call the tools. Save the connection JSON text in .mcp.json at the project root, or however the Vibe Coder saves the MCP server list locally.

### Prompt 2

> lets test each of your three MCP tools. Save the evidence in output/mcp_smoke.json. For every tool, include the prompt I asked, the tool name, the tool output must match values in data/campus_customs_new.db.

*What was lacking in Prompt 1:* it asked to connect and test the tools but did not ask for saved evidence that pairs each prompt and tool call with output checked against the working database.

## Problem 5: Build the agent team and grow the MCP tools

### Prompt 1

> Problem 5, build the agent team and grow the MCP tools. Build the agentic team for campus customs using Pydantic AI, bus, inventory, accounting, facilities, and customer service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompt in this folder, backend/prompt/. One file power agent. Put data types in backend/models.py. And the agent files under backend/. Your layout can vary as long as the five rows are clear. Use the port key API key and only GPT-6 Luna for every agent, like I said. Write every prompt with the shop rules that the agent needs. More detailed prompts that cover all aspects of an agent's work and scope score higher than a short generic prompt. So, we're going to be talking to each agent using our own words.

### Prompt 2

> All right, so let's add any tools the agents need to the MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db. Do not invent a second shop tools layer that bypasses MCP. Wire the agent so they append to output/audits_trail.json as they run. For each agent loop step, record enough to audit later. Append to this file, do not wipe it out each run. In output/harness.md, list each agent and each MCP tool, including ones you add in this problem, along with which table the tools uses. Also, add a short safety section, the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/readme.md so the tool list matches what you have now.

*What was lacking in Prompt 1:* it asked for the team and tools but did not require that all shop data flow only through MCP, an append-only audit trail of every agent step, a per-agent/per-tool table map, or a safety and token-limit section.

## Problem 6: Plan the three tickets

### Prompt 1

> Problem 6. Plan the three tickets. Before you wire the backend, write down what you expect the team to do on each open ticket. Build output slash desk underscore tickets dot html, a page I can double click with one tab per ticket, 101, 102, and 103. Also, add empty cache and reflection tabs for later problems. Leave them blank or with a short coming later note for now. On each ticket tab, fill an expected section only. Leave room for an actual section I will fill after you run the agent.

### Prompt 2

> For each ticket's expected section, write in your own words who the bus should call first and why. All the agents, delegations you expect, not bus calls everyone. Which MCP tools you expect that run to use. Plans that send every specialist on every ticket score low. So we must not do that. We will compare this plan to what actually happened when the agents resolved the three tickets.

*What was lacking in Prompt 1:* it asked for an expected outcome per ticket but not for a lean, explicit delegation plan (who the boss calls first and why, which specialists are left out, and which MCP tools each run should use) to compare against the real run.

## Problem 7: Backend routes

### Prompt 1

> Question 7. Backend route. Your React front-end dashboard, the next problem, needs a backend it can call in. In backend/main.py, use fast API and add routes that do the following. 1. Return the tree ticket and whether each is open or resolved. 2. Take a ticket ID and run your agent team on that ticket. 3. Return recent agent events, what each agent said and which tools they used, so the board can refresh. 4. Approve a payment or purchase after a human clicks approve. Agent only prepare the pay. This route is what actually changes cash. 5. Return the current check-in balance from cash_account. And 6. Reset the database to the original values when you want to try a fresh run.

### Prompt 2

> From the backend slash folder, start the server with: uvicorn main:app --reload --port 8000 This turns on your backend at http://localhost:8000. So the front-end dashboard can call those routes. In output/harness.md, list each route in one line with URL/what it does.

*What was lacking in Prompt 1:* it defined the routes but not how to start the server (from backend/ with `uvicorn main:app --reload --port 8000`) or a one-line-per-route reference for the dashboard.

## Problem 8: Agent dashboard

### Prompt 1

> . Problem 8. Agent dashboard. Build the front-end dashboard in front-end slash with React plus Vite plus TypeScript. The page should call the route you built in problem 7. At minimum, the board should list all three tickets, let you pick one ticket and start the agent team on it, show each agent and what they are saying or doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay or purchase when asked, show the check-in balance it should drop after an approved pay. Make the dashboard look good, be creative with the layout and feel. This is a real desk people would want to sit at, so put thought into how it looks.

### Prompt 2

> Tell the front end to talk to the back end at localhost:8000. On the back end, allow the pipe page origin, usually localhost:5173, so the browser is allowed to call those routes. Start the board with: npm run dev This opens the React desk in your browser so you can pick ticket and watch agents. Write output/design.md with what you choose for the dashboard look, layout, how agents read differently, how resolve tickets and cash show up, and why, including the creative choices that make it feel special and something humans would actually enjoy using.

*What was lacking in Prompt 1:* it asked for the dashboard but did not pin down how the browser reaches the backend (direct to localhost:8000 with CORS for the Vite origin), how to launch it, or a written design rationale.

## Problem 9: Resolve the tickets

### Prompt 1

> Problem 9. Resolve the ticket. Before testing the agent on a full run over the 3 tickets, you set the working database data/campus_customs_new.db. Again, so you start clean. Note the starting check-in balance, then run all 3 tickets on the board, 101, 102, 103, until each is resolved. Open output/desk_tickets.html from problem 6. On each ticket tab, fill the actual section from this run, which agents worked, what they delegated, and which tools they used. Keep your expected section so you can compare the two.

### Prompt 2

> On the cache tab of the same, output /desk_tickets.html, itemize the money. Number one, starting checking balance after the reset. Number two, for each ticket, how cash changed when that ticket resolved, and why. Which pay /purchase/dollar amount. Number three, ending checking balance. It must match #account in the working database. Wrong cash map loses points even if the board shows every ticket result, so check on that. Also, save output/result_tickets.json for each ticket. Include ID, final status, short outcome, what each agent contributed, and any human approvals. Then lastly, output/result_board.html, a page you can double-click with a screenshot of your React board for each reserve ticket 101, 102, 103. So let's append real runs to output_trail.json. Finish output/harness.md so it covers tables, MCP tools, the 5 agents, API routes, the dashboard, and safety rules.

*What was lacking in Prompt 1:* it ran and compared the tickets but did not ask for an itemized cash reconciliation checked against the database, machine-readable per-ticket results, screenshot evidence of the board, or a finished end-to-end harness.

## Problem 10: Reflection

### Prompt 1

> Problem 10, reflection. Open output/desk_tickets.html so i can fill the reflection tab. I'm going to answer in my own word a few things. these are the things I'm going to document. If you can add notes there for me to include my own thoughts. How would you evaluate the performance of the agent on each ticket and why? For each ticket, how did actual compare to the expected plan we wrote earlier? One would have been simpler as one agent with the tools and why. Describe three new problems Apple's customers might face that this agent team could solve with the tools you built. Describe three new problems campus customers might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them.

### Prompt 6

> ok good. push the code to github as a public url and also put it in output/github_url.txt

*What was lacking in Prompt 5:* it set up the model choice but not how the finished homework would be published and shared.

### Prompt 7

> heres the file layout, confirm this is what you did. remove anything private to me or my pc
>
> *(Attached: a screenshot of the required `hw5/` layout — `AI_prompts.md`, `requirements.txt`, `.env.example`, `.gitignore`, `.mcp.json`, `README.md`, `data/` (both DBs), `mcp_server/` (`server.py`, `README.md`), `frontend/`, `backend/` (`main.py`, `models.py`, `prompts/` with one file per agent), and `output/` (`harness.md`, `mcp_smoke.json`, `desk_tickets.html`, `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, `github_url.txt`) — plus: "README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full three-ticket run.")*

*What was lacking in Prompt 6:* it asked to publish the code but did not give the required file layout, the README contents, or say that personal and machine details must be removed first.
