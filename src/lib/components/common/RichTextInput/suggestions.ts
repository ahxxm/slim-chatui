import { createClassComponent } from 'svelte/legacy';
import { computePosition, flip, shift, offset } from '@floating-ui/dom';

export function getSuggestionRenderer(Component: any, ComponentProps = {}) {
	return function suggestionRenderer() {
		let component = null;
		let container: HTMLDivElement | null = null;
		let getClientRect: (() => DOMRect) | null = null;

		const virtualEl = {
			getBoundingClientRect: () => getClientRect?.() ?? new DOMRect()
		};

		const updatePosition = async () => {
			if (!container) return;
			const { x, y } = await computePosition(virtualEl, container, {
				placement: 'top-start',
				middleware: [
					offset({ mainAxis: -2, crossAxis: -10 }),
					flip({ fallbackPlacements: ['top-end', 'bottom-start', 'bottom-end'], padding: 8 }),
					shift({ padding: 8 })
				],
				strategy: 'fixed'
			});
			Object.assign(container.style, { left: `${x}px`, top: `${y}px` });
		};

		return {
			onStart: (props: any) => {
				getClientRect = props.clientRect;

				container = document.createElement('div');
				container.className = 'suggestion-list-container';
				container.style.cssText = 'position:fixed;z-index:9999';
				document.body.appendChild(container);

				component = createClassComponent({
					component: Component,
					target: container,
					props: {
						query: props?.query,
						command: (item) => {
							props.command({ id: item.id, label: item.label });
						},
						...ComponentProps
					},
					context: new Map<string, any>([['i18n', ComponentProps?.i18n]])
				});

				updatePosition();
			},

			onUpdate: (props: any) => {
				if (!component) return;

				component.$set({
					query: props.query,
					command: (item) => {
						props.command({ id: item.id, label: item.label });
					}
				});

				if (props.clientRect) {
					getClientRect = props.clientRect;
					updatePosition();
				}
			},

			onKeyDown: (props: any) => {
				// @ts-ignore
				return component?._onKeyDown?.(props.event) ?? false;
			},

			onExit: () => {
				try {
					component?.$destroy();
				} catch (e) {
					console.error('Error unmounting component:', e);
				}
				component = null;

				if (container?.parentNode) container.parentNode.removeChild(container);
				container = null;
				getClientRect = null;
			}
		};
	};
}
