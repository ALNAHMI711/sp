# Autonomous Cloud Execution & Control Hub

منصة سحابية خاصة للإدارة والتشغيل والمراقبة الآلية للمشاريع، مصممة لتعمل 24/7 دون اعتماد على اتصال الهاتف.

## الحالة

Repository جديد وفارغ عند بدء التنفيذ. هذه المرحلة تضع وثيقة المتطلبات ونقطة انطلاق قابلة للتتبع قبل تنفيذ البنية التشغيلية.

**Production Ready:** NO

## المبادئ

- Admin-only access
- GitHub as source of code
- Secure CI/CD with staging and health gates
- Dockerized services
- 24/7 cloud execution independent of phone connectivity
- Worker health, queueing and controlled failover
- Centralized logs and audit trail
- Secrets outside source control
- Backups with restore verification
- Kill switch and maintenance mode
- AI operations restricted by policy

## Lifecycle

`DISCOVERED → PENDING_APPROVAL → APPROVED → SYNCING → TESTING → BUILDING → STAGING → HEALTH_CHECK → PRODUCTION → MONITORED`

Failure paths include `FAILED`, `ROLLED_BACK`, and `DISABLED`.

## إعداد مفاتيح التكامل من لوحة التحكم

بعد تسجيل الدخول، افتح قسم **إعدادات التكامل والمفاتيح** وأدخل ما تحتاجه فقط: GitHub Webhook Secret، وGitHub App ID/Private Key، وTelegram Bot Token ومعرّفات المستخدمين المسموح لهم، ومفتاح مزود الذكاء الاصطناعي. القيم تحفظ مشفرة في قاعدة البيانات ولا يعيدها API إلى المتصفح؛ لوحة التحكم تعرض حالة الإعداد فقط. يمكن حذف أي مفتاح من القائمة.

مفتاح التشفير `control-secrets.key` يُنشأ على الخادم داخل مجلد البيانات الدائم بصلاحيات مقيدة، ولا يُدخل في اللوحة ولا يُرفع إلى GitHub. يجب حماية نسخة مجلد البيانات؛ فقدان مفتاح التشفير يمنع استعادة المفاتيح المحفوظة. بيانات التهيئة الأساسية للدخول وتوقيع الجلسات وقاعدة البيانات تبقى إعدادات تشغيل أولية، وليست مفاتيح تكامل.

## Security

Never commit passwords, API keys, tokens, or private keys. Integration credentials should be managed through the authenticated control panel; environment variables are optional fallback/bootstrap only. Production deployment must remain blocked until authentication, authorization, security checks, tests, health checks, rollback and operational controls are actually verified.

## Execution rule

Inspect → Implement → Test → Fix → Retest → Verify → Commit.

No mock health/connection/deployment status is considered valid production functionality.
