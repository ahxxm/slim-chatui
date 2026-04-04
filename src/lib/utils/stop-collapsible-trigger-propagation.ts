const COLLAPSIBLE_TRIGGER_SELECTOR = '[data-collapsible-trigger]';
const TRIGGER_EVENT_TYPES = ['click', 'keydown', 'pointerup'] as const;

const eventComesFromCollapsibleTrigger = (
	container: HTMLElement,
	target: EventTarget | null
): boolean => {
	if (!(target instanceof Node)) {
		return false;
	}

	const trigger = container.querySelector(COLLAPSIBLE_TRIGGER_SELECTOR);
	return trigger?.contains(target) ?? false;
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
