# HIKMA IMPACT v2

منصة Flask لإدارة وعرض أثر فريق الحكمة الطلابي.

## بنية النظام
- الموقع العام: بدون حساب للزوار.
- مركز الإدارة: `/admin/login` لصانع التطبيق والأدمن فقط.
- الأخبار والنشر: `/news` للعامة و`/admin/news` للإدارة.
- الصفحات المخصصة: `/admin/pages` مع عرض عام عبر `/page/<slug>`.
- الأعضاء والتقييمات والمبادرات والإنجازات: للعرض العام، بينما عمليات الإضافة والتعديل والحذف محمية.
- إعدادات المظهر: الألوان، الخط، Hero، شريط الإعلان وCSS مخصص.
- صلاحيات المستخدمين: `CREATOR` و`ADMIN`.
- صور الأعضاء: ترفع من مركز الإدارة إلى `static/uploads`.
- النسخ الاحتياطي: JSON من الإعدادات.

## التشغيل على Render
Build Command:
`pip install -r requirements.txt`

Start Command:
`gunicorn app:app`

يفضل ضبط:
`HIKMA_SECRET_KEY`

## ملاحظة قاعدة البيانات
المشروع يستخدم SQLite. في بيئة إنتاج حقيقية مع بيانات مهمة يفضل نقل قاعدة البيانات إلى PostgreSQL أو استخدام Persistent Disk مع خطة استضافة مناسبة.


## v3 account management
- Creator account: Abdulrahman.a.alani1@gmail.com
- Five initial admin accounts are provisioned by name and username; the Creator assigns their passwords from the Admin Accounts page.
- Creator-only logo upload for team/university/favicon.
- Public visitors remain view-only; write actions require admin authentication.
