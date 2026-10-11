# Autonomous Cloud Execution & Control Hub

منصة سحابية لإدارة مستودعات GitHub ومهام الفحص والتنفيذ المراقب من لوحة عربية RTL، مع فصل واجهة التحكم عن العامل (Worker). الهاتف عميل للتحكم فقط؛ التشغيل الدائم يتطلب نشر API والعامل وقاعدة البيانات على خادم مناسب.

## الحالة الحالية

- لوحة تحكم عربية لتسجيل الدخول، عرض الصحة وKill Switch، إرسال مهمة، متابعة Job، اعتماد المهمة أو إلغاؤها.
- API محمية بالمصادقة والصلاحيات، وقائمة مستودعات تنفيذ معتمدة منفصلة عن جرد مستودعات GitHub.
- جرد المستودعات العامة يعمل دون Token؛ يمكن إظهار الخاصة باستخدام `GITHUB_READ_TOKEN` محفوظ على الخادم.
- GitHub webhook يتحقق من توقيع SHA-256 ويحوّل push من مستودع معتمد إلى مهمة قراءة فقط بانتظار الموافقة.
- Queue يدعم SQLite وPostgreSQL؛ توجد اختبارات API وتكامل CI.
- **Production Ready: NO** — لا تعتبر المنصة منشورة أو عاملة 24/7 حتى يتم إعداد الأسرار وقاعدة البيانات والعامل والنشر وHTTPS، ثم اختبار المسار الكامل فعليًا.

## الإعداد المحلي

1. أنشئ بيئة Python وثبّت اعتماديات المشروع وفق ملفات الاعتماد في المستودع.
2. انسخ `.env.example` إلى `.env` واملأ القيم السرية محليًا. لا ترفع `.env` إلى Git.
3. اضبط `CONTROL_ADMIN_USERNAME` و`CONTROL_ADMIN_PASSWORD` و`CONTROL_JWT_SECRET` حسب `app/auth.py`. كلمة المرور تُخزّن كـ hash عند تهيئة المدير، ومفتاح JWT يجب أن يكون عشوائيًا قويًا؛ لا تستخدم قيمًا افتراضية أو ترفع الأسرار إلى Git.
4. شغّل API وفق تعليمات التشغيل الخاصة بالمشروع، ثم افتح ملف `dashboard/index.html` من خلال خادم الويب/الوكيل المهيأ للمسارات، وليس كملف ثابت منفصل عن API.
5. شغّل الاختبارات وراجع GitHub Actions قبل اعتماد أي نشر.

## إعداد جرد GitHub

- `GITHUB_OWNER=ALNAHMI711`: اسم المستخدم أو المالك الذي تريد عرض مستودعاته. عند وجود token يستخدم الجرد `/user/repos` ثم يفلتر النتائج على المالك المحدد؛ دون token يستخدم الجرد العام.
- `GITHUB_READ_TOKEN` اختياري. بدونه يعرض GitHub المستودعات العامة فقط. لعرض الخاصة، أنشئ Fine-grained token محدودًا للمالك والمستودعات المطلوبة، وبصلاحية **Metadata: read-only** فقط إذا كانت كافية لاحتياج الجرد.
- ضع الرمز في أسرار/متغيرات بيئة الخادم فقط، ولا ترسله في المحادثة ولا تضعه في الواجهة أو المستودع.
- ظهور المستودع في الجرد لا يمنحه إذن تنفيذ. قائمة التنفيذ منفصلة وتحددها سياسة الخادم `CONTROL_ALLOWED_REPOS`/آلية `approved_repositories()`.
- لا تستخدم رمزًا بصلاحية كتابة لمجرد عرض الجرد. توثيق الصلاحيات: [GitHub fine-grained token permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens).

## متغيرات التشغيل المهمة

- `CONTROL_QUEUE_BACKEND=sqlite|postgres`
- `CONTROL_QUEUE_DB` مسار SQLite المحلي.
- `CONTROL_POSTGRES_DSN` مطلوب عند اختيار PostgreSQL.
- `CONTROL_KILL_SWITCH_FILE` ملف إيقاف استقبال المهام الجديدة.
- `GITHUB_WEBHOOK_SECRET` سر عشوائي قوي للتحقق من توقيع webhook.
- `AI_API_KEY` و`TELEGRAM_BOT_TOKEN` اختياريان، ويجب حفظهما على الخادم فقط.

## تشغيل لوحة التحكم عبر Docker Compose

هذا إعداد VPS ذاتي الاستضافة، وليس نشرًا تلقائيًا على خدمة مجانية:

1. ثبّت Docker Engine وDocker Compose على VPS يدعم تشغيل الحاويات.
2. انسخ `.env.example` إلى `.env`، وانسخ `deploy/worker.env.example` إلى `deploy/worker.env`، ثم عيّن قيمًا قوية وفريدة لـ `CONTROL_ADMIN_PASSWORD` و`CONTROL_JWT_SECRET` و`GITHUB_WEBHOOK_SECRET` و`POSTGRES_PASSWORD`. املأ إعدادات OpenHands في `deploy/worker.env` إذا أردت تفعيل منفّذ المهام. لا ترفع أيًا من الملفين الفعليين إلى Git.
3. جهّز شهادة TLS صالحة لنطاقك وضع `fullchain.pem` و`privkey.pem` في مجلد `tls` (أو اضبط `CONTROL_TLS_DIR` إلى مسار آخر). لا تستخدم شهادة وهمية في الإنتاج.
4. شغّل من جذر المستودع:

```bash
docker compose --env-file .env -f deploy/compose.control-plane.yml up -d --build
docker compose --env-file .env -f deploy/compose.control-plane.yml ps
docker compose --env-file .env -f deploy/compose.control-plane.yml logs --tail=100 control-api nginx worker
```

5. وجّه DNS للنطاق إلى عنوان VPS، وافتح TCP 80/443 فقط للويب، وقيّد SSH إلى عناوين الإدارة الموثوقة.
6. افتح النطاق عبر HTTPS واختبر تسجيل الدخول، الصحة، إنشاء مهمة، الموافقة، الإلغاء، وسجل التدقيق قبل الاستخدام.

يخدم Nginx مجلد `dashboard/` ويحوّل `/api/*` إلى API، ويحوّل HTTP إلى HTTPS. يحدّ الوكيل محاولات تسجيل الدخول إلى 5 طلبات في الدقيقة لكل عنوان IP مع سماح اندفاعي محدود، ويضيف ترويسات حماية للمتصفح. يحتاج Nginx إلى الشهادة قبل بدء التشغيل. لا تعني حالة الحاوية `healthy` أن جميع التكاملات الخارجية جاهزة.

### اختيار قاعدة البيانات

- الوضع الافتراضي `CONTROL_QUEUE_BACKEND=sqlite` للتجارب والعقدة الواحدة.
- لاستخدام PostgreSQL، اضبط `CONTROL_QUEUE_BACKEND=postgres` و`CONTROL_POSTGRES_DSN=postgresql://controlhub:<password>@postgres:5432/controlhub`؛ يجب أن يطابق اسم المستخدم/قاعدة البيانات كلمة المرور في متغيرات `POSTGRES_*`. إذا احتوت كلمة المرور على رموز خاصة فيجب ترميزها داخل DSN.
- احتفظ بنسخ احتياطية مشفرة واختبر الاستعادة. لا تعتمد على حجم Docker volume وحده كخطة نسخ احتياطي.

## الأمان وحدود التنفيذ

- المهام تبدأ بحالة `pending_approval`؛ لا تُشغّل أعمال حساسة دون موافقة.
- Kill Switch يمنع إنشاء مهام جديدة، ولا يعني إيقافًا فوريًا أو آمنًا لكل عامل خارجي.
- لا تضع أسرارًا في السجلات أو طلبات المتصفح أو Git.
- لا توصل عاملًا قادرًا على تشغيل أوامر مستودع مباشرة بالإنترنت العام دون عزل وصلاحيات محدودة وحدود موارد ومراجعة للمخرجات.
- لا تعتبر حالة الصحة أو نجاح CI بديلًا عن اختبار النشر الفعلي، استعادة النسخ الاحتياطية، أو اختبار rollback.

## معايير الإطلاق

قبل إعلان Production Ready يجب التحقق فعليًا من: HTTPS، إعدادات المدير والجلسات، RBAC، عزل العامل، موافقة المهام، PostgreSQL persistence، النسخ الاحتياطي والاستعادة، سجلات تدقيق بلا أسرار، حدود الشبكة وSSRF، مراقبة العامل، rollback، واختبارات من بيئة نشر نظيفة.

## قاعدة العمل

Inspect → Implement → Test → Fix → Retest → Verify → Commit. لا يتم الادعاء بنجاح أي اتصال أو نشر غير مختبر.
