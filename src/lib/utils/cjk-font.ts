// cn-font-split, github.com/CMBill/lxgw-wenkai-screen-web
const CDN_ID = 'lxgw-wenkai-screen-cdn';
const CDN_URL = 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-web/lxgwwenkaiscreen/result.css';
const LXGW = "'LXGW WenKai Screen', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC'";
const DEFAULT = "'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC'";

export function applyCjkFont(value: string) {
	if (typeof document === 'undefined') return;

	const existing = document.getElementById(CDN_ID);
	if (value === 'lxgw') {
		if (!existing) {
			const link = document.createElement('link');
			link.id = CDN_ID;
			link.rel = 'stylesheet';
			link.href = CDN_URL;
			document.head.appendChild(link);
		}
		document.documentElement.style.setProperty('--font-cjk', LXGW);
	} else {
		existing?.remove();
		document.documentElement.style.setProperty('--font-cjk', DEFAULT);
	}
}
