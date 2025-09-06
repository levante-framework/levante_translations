function ensureAudioValidationButton() {
	try {
		const bar = document.querySelector('.validation-controls');
		if (!bar) return;
		if (bar.querySelector('.audio-validation-btn')) return;
		const btn = document.createElement('button');
		btn.className = 'btn btn-info btn-compact audio-validation-btn';
		btn.innerHTML = '<i class="fas fa-wave-square"></i> Audio Validation';
		btn.onclick = (e) => { e.preventDefault(); window.open('./audio-validation.html', '_blank'); return false; };
		bar.appendChild(btn);
	} catch (e) { console.warn('ensureAudioValidationButton error', e); }
}

function retargetValidationViewButton() {
	try {
		const viewBtn = document.getElementById('viewValidations');
		if (viewBtn) {
			viewBtn.innerHTML = '<i class="fas fa-wave-square"></i> Audio Validation';
			viewBtn.onclick = (e) => { e.preventDefault(); window.open('./audio-validation.html', '_blank'); return false; };
			return;
		}
		ensureAudioValidationButton();
	} catch (e) { console.warn('retargetValidationViewButton error', e); }
}

// Hook into dashboard lifecycle after tabs and tables populate
(function hookToolbar() {
	const origCreateTabs = window.Dashboard?.prototype?.createTabs;
	if (!origCreateTabs) return;
	window.Dashboard.prototype.createTabs = function() {
		origCreateTabs.apply(this, arguments);
		setTimeout(() => { retargetValidationViewButton(); ensureAudioValidationButton(); }, 200);
	};
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', () => setTimeout(() => { retargetValidationViewButton(); ensureAudioValidationButton(); }, 200));
	} else {
		setTimeout(() => { retargetValidationViewButton(); ensureAudioValidationButton(); }, 200);
	}
})();
