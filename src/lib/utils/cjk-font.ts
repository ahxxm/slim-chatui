// cn-font-split fonts:
// github.com/CMBill/lxgw-wenkai-screen-web
// github.com/fontsource/fontsource (Noto Sans SC)
const CDN_LINK_ID = 'cjk-font-cdn';
const SYSTEM_FALLBACK = "'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC'";

const CJK_FONTS: Record<string, { css: string; family: string }> = {
	lxgw: {
		css: 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-web/lxgwwenkaiscreen/result.css',
		family: "'LXGW WenKai Screen'"
	},
	noto: {
		css: 'https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc/400.css',
		family: "'Noto Sans SC'"
	}
};

export function applyCjkFont(value: string) {
	if (typeof document === 'undefined') return;

	document.getElementById(CDN_LINK_ID)?.remove();

	const font = CJK_FONTS[value];
	if (font) {
		const link = document.createElement('link');
		link.id = CDN_LINK_ID;
		link.rel = 'stylesheet';
		link.href = font.css;
		document.head.appendChild(link);
		document.documentElement.style.setProperty('--font-cjk', `${font.family}, ${SYSTEM_FALLBACK}`);
	} else {
		document.documentElement.style.setProperty('--font-cjk', SYSTEM_FALLBACK);
	}
}
