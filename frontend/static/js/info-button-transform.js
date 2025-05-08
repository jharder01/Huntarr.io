/**
 * Transform INFO badges into Font Awesome icons
 * - Moves from right to left of the title
 * - Converts from badge to icon
 * - Hides on mobile (via CSS)
 */
document.addEventListener('DOMContentLoaded', function() {
    // Function to transform the INFO badges into icons
    function transformInfoBadges() {
        // Target badges within the history table body for specificity
        const infoBadges = document.querySelectorAll('#historyTableBody td .title-with-info span.info-badge');

        infoBadges.forEach(badge => {
            // Idempotency check: if already an icon, skip
            if (badge.classList.contains('info-icon')) {
                return;
            }

            // Clear existing text (e.g., "info")
            badge.textContent = '';

            // Add Font Awesome and custom classes
            badge.classList.add('fas', 'fa-circle-info', 'info-icon');
            // Note: The 'info-badge' class is kept to retain original event listeners from history.js

            // Move the icon to the beginning of its parent '.title-with-info' container
            const titleContainer = badge.closest('.title-with-info');
            if (titleContainer) {
                titleContainer.insertBefore(badge, titleContainer.firstChild);
            }
        });
    }

    // Initial transformation on page load
    transformInfoBadges();

    // Set up a MutationObserver to handle dynamically loaded history items
    const historyTableBody = document.getElementById('historyTableBody');
    if (historyTableBody) {
        const observer = new MutationObserver(function(mutationsList, observer) {
            // Call transformInfoBadges whenever new nodes are added or the subtree changes
            // This ensures new history entries also get their info badges transformed.
            for (const mutation of mutationsList) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    transformInfoBadges();
                    break; // No need to check other mutations if one relevant change is found
                }
            }
        });

        observer.observe(historyTableBody, { childList: true, subtree: true });
    } else {
        console.warn('History table body (#historyTableBody) not found for MutationObserver.');
    }

    // jQuery :contains polyfill (can be removed if not used elsewhere, but kept for safety for now)
    // This was part of the original script, might be used by other parts or was for a broader selection initially.
    if (window.jQuery) {
        jQuery.expr[':'].contains = function(a, i, m) {
            return jQuery(a).text().toUpperCase().indexOf(m[3].toUpperCase()) >= 0;
        };
    }
});
