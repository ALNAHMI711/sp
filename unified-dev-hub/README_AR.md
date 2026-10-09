# مركز التطوير الموحد

نسخة مستقلة قابلة للتشغيل محليًا أو عبر Docker، لإدارة المشاريع البرمجية من لوحة عربية RTL.

## الميزات
- لوحة عربية متجاوبة لإدارة المشاريع ومراحلها.
- تسجيل دخول إداري بكلمة مرور تُضبط عبر متغير بيئة، مع جلسة موقعة.
- قاعدة SQLite دائمة داخل مجلد البيانات.
- API لإنشاء المشاريع وتحديث المرحلة وحذف المشروع، محمية بتسجيل الدخول.
- سجل تدقيق للأحداث.
- فحص صحة الخدمة على `/health`.
- اختبارات تلقائية وCI عبر GitHub Actions.

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

## تشغيل عبر Docker
```bash
cp .env.example .env
# عدّل كلمات المرور والمفتاح السري أولًا
docker compose up --build -d
```

## الإعدادات
- `ADMIN_USERNAME`: اسم المدير.
- `ADMIN_PASSWORD`: كلمة مرور المدير (يجب تغيير القيمة الافتراضية).
- `SECRET_KEY`: مفتاح جلسة عشوائي طويل.
- `DATABASE_PATH`: مسار ملف SQLite.
- `COOKIE_SECURE`: اجعله `true` خلف HTTPS.

## الأمان وحدود النسخة
- لا تضع مفاتيح GitHub أو Vercel أو أي أسرار داخل Git.
- تكاملات GitHub/Vercel الفعلية ليست مفعّلة تلقائيًا؛ أضفها لاحقًا عبر أسرار الخادم وواجهات موثقة.
- هذه النسخة لا تنفّذ أوامر بناء/نشر عن بُعد ولا تدّعي نجاح CI أو النشر؛ إنها لوحة إدارة مشاريع مستقلة قابلة للتوسعة.
- استخدم HTTPS عند النشر العام، واضبط `SECRET_KEY` وبيانات المدير قبل التشغيل.
