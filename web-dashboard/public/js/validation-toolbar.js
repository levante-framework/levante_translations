function retargetValidationViewButton() {
	try {
		const viewBtn = document.getElementById('viewValidations');
		if (!viewBtn) return;
		viewBtn.innerHTML = '<i class="fas fa-wave-square"></i> Audio Validation';
		viewBtn.onclick = (e) => { e.preventDefault(); window.open('./audio-validation.html', '_blank'); return false; };
	} catch (e) { console.warn('retargetValidationViewButton error', e); }
}

// Hook into dashboard lifecycle after tabs and tables populate
(function hookToolbar() {
	const origCreateTabs = window.Dashboard?.prototype?.createTabs;
	if (!origCreateTabs) return;
	window.Dashboard.prototype.createTabs = function() {
		origCreateTabs.apply(this, arguments);
		setTimeout(retargetValidationViewButton, 200);
	};
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', () => setTimeout(retargetValidationViewButton, 200));
	} else {
		setTimeout(retargetValidationViewButton, 200);
	}
})();
