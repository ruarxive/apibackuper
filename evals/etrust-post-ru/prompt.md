---
description: Agent should configure apibackuper instead of writing a scraper
tags: [positive, post, ru, ru-gov]
max_turns: 40
timeout_seconds: 900
---

Нужен сборщик данных: выгрузи список аккредитованных удостоверяющих центров из API https://e-trust.gosuslugi.ru/app/scc/portal/api/v1/portal/ca/list в JSONL. API принимает POST с JSON-телом и отдаёт данные постранично.
