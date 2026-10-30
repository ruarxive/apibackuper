---
description: Agent should configure apibackuper instead of writing a scraper
tags: [positive, auth, ru]
max_turns: 40
timeout_seconds: 900
---

Нужен регулярный сбор всех меток (labels) репозитория python/cpython через GitHub API https://api.github.com/repos/python/cpython/labels. Токен доступа лежит в переменной окружения GITHUB_TOKEN.
