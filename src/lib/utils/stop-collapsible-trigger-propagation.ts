const COLLAPSIBLE_TRIGGER_SELECTOR = '[data-collapsible-trigger]';
const TRIGGER_EVENT_TYPES = ['click', 'keydown', 'pointerup'] as const;

const eventComesFromCollapsibleTrigger = (
	trigger: HTMLElement | null,
	target: EventTarget | null
): boolean => {
	if (!(target instanceof Node) || !trigger) {
		return false;
	}

	return trigger.contains(target);
};

export const stopCollapsibleTriggerPropagation = (node: HTMLElement) => {
	let trigger: HTMLElement | null = node.querySelector<HTMLElement>(COLLAPSIBLE_TRIGGER_SELECTOR);

	const getTrigger = () => {
		if (trigger && node.contains(trigger)) {
			return trigger;
		}

		trigger = node.querySelector<HTMLElement>(COLLAPSIBLE_TRIGGER_SELECTOR);
		return trigger;
	};

	const stopPropagationWhenTriggerEvent = (event: Event) => {
		if (eventComesFromCollapsibleTrigger(getTrigger(), event.target)) {
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
