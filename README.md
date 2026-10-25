# فريق الحكمة + — منظومة إدارة الفريق والمبادرات

## أبرز تعديلات V26
- الاسم الرسمي في الواجهة: **فريق الحكمة +**.
- القائمة العامة مخفية وتفتح من زر ☰ المثبت في زاوية الشاشة.
- إزالة أزرار الوضع الليلي/النهاري من الواجهة العامة والإدارة.
- تقليل أزرار الانضمام إلى زر رئيسي واحد في الـ Hero.
- واجهة عامة سينمائية رسمية بطابع فضائي مع نجوم/مدار وإضاءة وحركة نزول تدريجية للنصوص.
- إصلاح تسجيل دخول الإدارة: البريد/اسم المستخدم مع الرمز يعملان بالحفظ المستقر، ولا يعاد تغيير رمز المالك عند كل Restart/Deploy.
- إضافة `password_plain` لدعم الرمز المخزن مباشرة بناءً على طلب المالك، مع الإبقاء على توافق كلمات المرور القديمة المشفرة.
- لا يوجد تحقق من الشهادات، ولا QR للحضور أو المبادرات.
- الحضور والمبادرات يدويان، مع تسجيل وقت الدخول والخروج الحالي وحساب الساعات.

## Render
استخدم نفس إعدادات الخدمة الحالية، وتأكد من وجود Persistent Disk إذا أردت بقاء SQLite والملفات المرفوعة بعد إعادة التشغيل.


## V26 FINAL FIXES
- إصلاح حفظ إعدادات الهوية والألوان والخلفيات بإزالة النماذج المتداخلة.
- حفظ الشعارات والصور المرفوعة مع عرضها بعد الحفظ.
- ماسح QR بالكاميرا داخل المنصة للحضور والمهام والفعاليات والمعدات، مع تسجيل الوقت والتاريخ تلقائيًا.
- استلام/إرجاع المعدات عبر مسح بطاقة العضو: إذا توجد عهدة مفتوحة تُسجل عودة، وإلا تُسجل عملية استلام.
- إصلاح/تحصين إصدار الشهادات وتسجيل الاستثناءات، مع A4 أفقي وتعديل كامل للنصوص والألوان والخطوط والشعارات واسم الكاتب.
- تحسين PDF الشامل مع شريط هوية أزرق ومسار fallback يمنع ظهور Internal Server Error للمستخدم.
- إضافة معاينة طباعة لقوالب البطاقات، مع ألوان وأحجام وخطوط وشعار قابلة للحفظ.
- قائمة الشرف تدعم معرض صور متعدد لكل شخص.
- الأكاديمية تقبل رفع الفيديو والصور مباشرة بدل الروابط.
- النسخة الاحتياطية الكاملة محدثة إلى V26 وتشمل الجداول الموسعة والملفات.
- إزالة واجهة قسم الإشعارات من لوحة الإدارة لتخفيف الواجهة.
- الحفاظ على القائمة الإدارية على اليسار والمظهر السينمائي الداكن.

## V43
Final implementation pass: certificate element positioning persistence, certificate reissue preservation, and removal of per-message notification creation. See V43_FINAL_AUDIT.md.


## إعدادات الأمان في نسخة فريق الحكمة +
- عيّن `HIKMA_SECRET_KEY` كسر طويل عشوائي في إعدادات الاستضافة.
- عيّن `HIKMA_OWNER_EMAIL=alhikmaplus@gmail.com` و`HIKMA_OWNER_PASSWORD` من لوحة الأسرار. لا تحفظ كلمة المرور في الكود.
- عيّن `HIKMA_DATA_DIR` على قرص دائم حتى لا تضيع قاعدة البيانات والملفات عند إعادة النشر.
- في تثبيت جديد دون كلمة مرور مالك مُهيأة، تُنشأ كلمة مرور عشوائية مؤقتة داخل `initial_owner_password.txt` بصلاحيات ملف خاصة. انقلها بأمان ثم عيّن السر في بيئة الاستضافة.
- كلمات المرور تحفظ كتجزئة آمنة؛ لا يعتمد تسجيل الدخول على `password_plain`.


## Production deployment hardening — V44

### Render deployment
- A `render.yaml` blueprint is included with Gunicorn, health checks, generated secret values, and a persistent `/data` disk.
- The persistent disk is required to preserve SQLite data, uploaded assets, and the local fallback secret across deployments.
- Keep `HIKMA_SECRET_KEY` and `HIKMA_OWNER_PASSWORD` in the hosting provider's secret/environment settings. Never commit real credentials.
- The Render blueprint uses a Starter web service because persistent disks may require a paid plan. Confirm current hosting plan and disk pricing before applying it.
- Health checks: `/healthz` (process) and `/readyz` (database readiness).

### Security and operations
- Production cookies use `HttpOnly`, `Secure`, and `SameSite=Lax`.
- Adds baseline browser security headers, same-origin checks for browser writes, and an IP-based failed-login cooldown after eight failures in a 15-minute window.
- Generic public asset delivery refuses files whose names start with `task-`; private task attachments must be downloaded through the authenticated route.
- JSON backup export/import now checks the `backup` permission and includes the collaboration tables.
- Full ZIP restore validates archive entry paths, blocks symlinks and unexpected file names, limits the number of files and expanded size, and checks SQLite integrity before restore.
- Backups contain personal and operational data. Store them privately and test restore on a separate staging copy before relying on them.

### Required pre-launch checklist
1. Set the owner email and a strong unique owner password in hosting secrets.
2. Verify `/readyz` returns HTTP 200 after deployment.
3. Test admin login, role permissions, task upload/download, member profiles, announcements, and live-room permissions.
4. Export a backup, restore it on a staging copy, and compare record counts and file availability.
5. Test live video and screen sharing from two separate networks over HTTPS; configure TURN if direct WebRTC connectivity fails.
6. Confirm persistent storage is mounted and that records and uploads survive a redeploy.
7. Review hosting logs and run `python -m unittest discover -s tests -v` in an environment with dependencies installed.

The build environment used to prepare this ZIP has no network access and does not have Flask/Werkzeug installed, so runtime integration tests could not be executed here. Do not treat static checks alone as proof of a successful production deployment.
\n\n### Docker\nA non-root `Dockerfile` and `.dockerignore` are included. Build from the project directory with `docker build -t hikma-plus .`, then provide the required secret environment variables and mount a persistent volume at `/data`. The container trusts one reverse-proxy hop by default; deploy it behind your own trusted TLS proxy.\n