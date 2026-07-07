(function() {
    if (typeof django === 'undefined' || !django.jQuery) {
        return;
    }

    const INLINE_SELECTOR = 'div.inline-related';
    const MIN_OVERFLOW_X = 1;
    const MIN_OVERLAY_WIDTH = 40;
    const NATIVE_SCROLLBAR_VISIBILITY_MARGIN = 6;

    function rafThrottle(callback) {
        let framePending = false;
        return function throttled() {
            if (framePending) {
                return;
            }
            framePending = true;
            window.requestAnimationFrame(() => {
                framePending = false;
                callback();
            });
        };
    }

    django.jQuery(function($) {
        const $body = $('body');
        if (!$body.length) {
            return;
        }

        const $overlay = $(
            '<div class="floating-inline-scrollbar" aria-hidden="true"><div class="floating-inline-scrollbar__content"></div></div>',
        );
        const $overlayContent = $overlay.find('.floating-inline-scrollbar__content');
        $overlay.css({
            position: 'fixed',
            bottom: '0',
            height: '16px',
            overflowX: 'scroll',
            overflowY: 'hidden',
            zIndex: 1200,
            display: 'none',
            borderTop: '1px solid var(--hairline-color)',
            background: 'rgba(255, 255, 255, 0.92)',
        });
        $overlayContent.css({
            height: '1px',
        });
        $body.append($overlay);

        let activeContainer = null;
        let activeScrollElement = null;
        let syncingFromOverlay = false;
        let syncingFromContainer = false;
        const boundScrollableElements = new WeakSet();

        function getHorizontalOverflow(element) {
            if (!element || element.clientWidth <= 0) {
                return 0;
            }

            return Math.max(0, element.scrollWidth - element.clientWidth);
        }

        function isHorizontallyScrollable(element) {
            return getHorizontalOverflow(element) > MIN_OVERFLOW_X;
        }

        function getScrollableElement(container) {
            if (!container) {
                return null;
            }

            const elements = [container].concat(Array.from(container.querySelectorAll('*')));
            let best = null;
            let bestOverflow = 0;

            elements.forEach((element) => {
                if (!isHorizontallyScrollable(element)) {
                    return;
                }

                const overflow = getHorizontalOverflow(element);
                if (overflow > bestOverflow) {
                    best = element;
                    bestOverflow = overflow;
                }
            });

            return best;
        }

        function isVisibleInViewport(rect) {
            return rect.bottom > 0 && rect.top < window.innerHeight;
        }

        function isNativeScrollbarVisible(scrollElementRect) {
            return (
                scrollElementRect.bottom >= -NATIVE_SCROLLBAR_VISIBILITY_MARGIN
                && scrollElementRect.bottom <= window.innerHeight + NATIVE_SCROLLBAR_VISIBILITY_MARGIN
            );
        }

        function buildCandidate(container) {
            const scrollElement = getScrollableElement(container);
            if (!scrollElement) {
                return null;
            }

            const rect = container.getBoundingClientRect();
            if (!isVisibleInViewport(rect)) {
                return null;
            }

            const scrollRect = scrollElement.getBoundingClientRect();
            if (isNativeScrollbarVisible(scrollRect)) {
                return null;
            }

            return {
                container,
                scrollElement,
                rect,
            };
        }

        function getCandidates() {
            return $(INLINE_SELECTOR)
                .toArray()
                .map(buildCandidate)
                .filter(Boolean);
        }

        function pickCandidate(candidates) {
            if (!candidates.length) {
                return null;
            }

            if (activeContainer) {
                const existing = candidates.find((candidate) => candidate.container === activeContainer);
                if (existing) {
                    return existing;
                }
            }

            const aboveFold = candidates.filter((candidate) => candidate.rect.top <= window.innerHeight);
            if (!aboveFold.length) {
                return candidates[0];
            }

            return aboveFold.reduce((best, current) => {
                return current.rect.top > best.rect.top ? current : best;
            });
        }

        function setOverlayVisibility(visible) {
            $overlay.toggleClass('is-visible', visible);
            $body.toggleClass('has-floating-inline-scrollbar', visible);
            if (visible) {
                $overlay.show();
            } else {
                $overlay.hide();
            }
        }

        function hideOverlay() {
            setOverlayVisibility(false);
            activeContainer = null;
            activeScrollElement = null;
        }

        function showOverlayFor(candidate) {
            const { container, scrollElement, rect } = candidate;

            const left = Math.max(0, rect.left);
            const width = Math.min(rect.width, Math.max(0, window.innerWidth - left));

            if (width < MIN_OVERLAY_WIDTH) {
                hideOverlay();
                return;
            }

            activeContainer = container;
            activeScrollElement = scrollElement;
            $overlay.css({
                left: left + 'px',
                width: width + 'px',
            });
            $overlayContent.width(scrollElement.scrollWidth);

            if (!syncingFromContainer) {
                syncingFromOverlay = true;
                $overlay.scrollLeft(scrollElement.scrollLeft);
                syncingFromOverlay = false;
            }

            setOverlayVisibility(true);
        }

        function bindInlineScrollHandlers() {
            $(INLINE_SELECTOR).each((_, element) => {
                const scrollElement = getScrollableElement(element);
                if (!scrollElement || boundScrollableElements.has(scrollElement)) {
                    return;
                }

                boundScrollableElements.add(scrollElement);
                $(scrollElement).on('scroll.floatingInlineScrollbar', () => {
                    if (syncingFromOverlay) {
                        return;
                    }

                    if (scrollElement === activeScrollElement) {
                        syncingFromContainer = true;
                        $overlay.scrollLeft(scrollElement.scrollLeft);
                        syncingFromContainer = false;
                    }

                    updateOverlay();
                });
            });
        }

        const updateOverlay = rafThrottle(() => {
            bindInlineScrollHandlers();

            const candidates = getCandidates();
            const selected = pickCandidate(candidates);

            if (!selected) {
                hideOverlay();
                return;
            }

            showOverlayFor(selected);
        });

        $overlay.on('scroll.floatingInlineScrollbar', () => {
            if (!activeScrollElement || syncingFromContainer) {
                return;
            }

            syncingFromOverlay = true;
            activeScrollElement.scrollLeft = $overlay.scrollLeft();
            syncingFromOverlay = false;
        });

        $(document).on('focusin.floatingInlineScrollbar', (event) => {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }

            const container = $(target).closest(INLINE_SELECTOR).get(0);
            if (container && getScrollableElement(container)) {
                activeContainer = container;
                updateOverlay();
            }
        });

        $(window).on('scroll.floatingInlineScrollbar resize.floatingInlineScrollbar load.floatingInlineScrollbar', updateOverlay);

        const observer = new MutationObserver(updateOverlay);
        observer.observe($body.get(0), {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['style', 'class'],
        });

        updateOverlay();
    });
})();
