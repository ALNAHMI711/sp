# مركز التطوير الموحد

نسخة مستقلة قابلة للتشغيل محليًا أو عبر Docker، لإدارة المشاريع البرمجية من لوحة عربية RTL.

## الميزات
- لوحة عربية متجاوبة لإدارة المشاريع ومراحلها.
- تسجيل دخول إداري بكلمة مرور تُضبط عبر متغير بيئة، مع جلسة موقعة.
- قاعدة SQLite دائمة داخل مجلد البيانات.
- API لإنشاء المشاريع وتحديث المرحلة وحذف المشروع، محمية بتسجيل الدخول.
- سجل تدقيق للأحداث.
- فحص صحة الخدمة على `/health`.
- صفحة تكاملات للقراءة فقط تعرض حالة اتصال GitHub وVercel، ومستودعات GitHub ومشاريع Vercel التي يمكن للرموز الوصول إليها.
- اختبارات تلقائية وCI عبر GitHub Actions مع حزمة ZIP قابلة للتنزيل من الـ workflow artifact.

## تشغيل سريع باستخدام Python
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# غيّر ADMIN_PASSWORD و SECRET_KEY في .env قبل الاستخدام
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
افتح `http://localhost:8000`.

## تشغيل الاختبارات
```bash
pip install -r requirements-dev.txt
pytest -q
```

## تشغيل عبر Docker
```bash
cp .env.example .env
# عدّل كلمات المرور والمفتاح السري أولًا
docker compose up --build -d
```

## الإعدادات
- `ADMIN_USERNAME`: اسم المدير.
- `ADMIN_PASSWORD`: كلمة مرور المدير (يجب تغيير القيمة الافتراضية).
- `SECRET_KEY`: مفتاح جلسة عشوائي لا يقل عن 32 حرفًا.
- `DATABASE_PATH`: مسار ملف SQLite.
- `COOKIE_SECURE`: اجعله `true` خلف HTTPS.

لإنشاء مفتاح سري عشوائي محليًا:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
- `GITHUB_READ_TOKEN`: اختياري؛ رمز قراءة لاستعراض مستودعات GitHub.
- `VERCEL_READ_TOKEN`: اختياري؛ رمز قراءة لاستعراض مشاريع Vercel.

## الأمان وحدود النسخة
- لا تضع مفاتيح GitHub أو Vercel أو أي أسرار حقيقية داخل Git أو الواجهة الأمامية.
- صفحة التكاملات لا تعرض الرموز ولا تنفذ عمليات كتابة أو نشر؛ وظائفها فحص الاتصال واستعراض الموارد للقراءة فقط.
- هذه النسخة لا تنفّذ أوامر بناء/نشر عن بُعد ولا تدّعي نجاح CI أو النشر؛ إنها لوحة إدارة مشاريع مستقلة قابلة للتوسعة.
- استخدم HTTPS عند النشر العام، واضبط `SECRET_KEY` وبيانات المدير قبل التشغيل.
- راجع `SECURITY.md` و`DEPLOYMENT.md` و`INTEGRATIONS.md` قبل النشر.
