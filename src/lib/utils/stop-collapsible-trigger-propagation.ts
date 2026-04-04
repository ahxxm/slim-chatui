const COLLAPSIBLE_TRIGGER_SELECTOR = '[data-collapsible-trigger]';
const TRIGGER_EVENT_TYPES = ['click', 'keydown', 'pointerup'] as const;

const eventComesFromCollapsibleTrigger = (
	container: HTMLElement,
	target: EventTarget | null
): boolean => {
	const targetElement =
		target instanceof Element ? target : target instanceof Node ? target.parentElement : null;

	if (!targetElement) {
		return false;
	}

	const trigger = targetElement.closest<HTMLElement>(COLLAPSIBLE_TRIGGER_SELECTOR);
	return trigger !== null && container.contains(trigger);
};

export const stopCollapsibleTriggerPropagation = (node: HTMLElement) => {
	const stopPropagationWhenTriggerEvent = (event: Event) => {
		if (eventComesFromCollapsibleTrigger(node, event.target)) {
			event.stopPropagation();
		}
	};

	for (const eventType of TRIGGER_EVENT_TYPES) {
		node.addEventListener(eventType, stopPropagationWhenTriggerEvent);
	}

	return {
		destroy() {
			for (const eventType of TRIGGER_EVENT_TYPES) {
				node.removeEventListener(eventType, stopPropagationWhenTriggerEvent);
			}
		}
	};
};
