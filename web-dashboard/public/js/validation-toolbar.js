function injectAudioValidationButton() {
	try {
		// For each table header, append a right-aligned button
		document.querySelectorAll('.data-table .table-header').forEach(header => {
			if (header.querySelector('.audio-validation-btn')) return;
			const btn = document.createElement('button');
			btn.className = 'btn btn-info audio-validation-btn';
			btn.style.marginLeft = 'auto';
			btn.innerHTML = '<i class="fas fa-wave-square"></i> Audio Validation';
			btn.onclick = openAudioValidationModal;
			header.style.display = 'flex';
			header.style.alignItems = 'center';
			header.style.gap = '10px';
			header.appendChild(btn);
		});
	} catch (e) { console.warn('injectAudioValidationButton error', e); }
}

// Hook into dashboard lifecycle after tabs and tables populate
(function hookToolbar() {
	const origCreateTabs = window.Dashboard?.prototype?.createTabs;
	if (!origCreateTabs) return;
	window.Dashboard.prototype.createTabs = function() {
		origCreateTabs.apply(this, arguments);
		setTimeout(injectAudioValidationButton, 200);
	};
})();
