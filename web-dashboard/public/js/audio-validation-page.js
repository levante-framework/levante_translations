(function(){
	const { createApp, ref, computed, onMounted } = Vue;

	function base(path){ const i=(path||'').lastIndexOf('/'); return i>=0?path.slice(i+1):path; }
	function stripExt(n){ return (n||'').replace(/\.[a-zA-Z0-9]+$/, ''); }
	
	function extractLangsFromPath(audioPath){
		const langs=new Set(); const p=audioPath||'';
		let m=p.match(/(?:audio_files|audio)\/([A-Za-z-]{2,10})\//); if(m&&m[1]){ langs.add(m[1]); if(m[1].includes('-')) langs.add(m[1].split('-')[0]); }
		p.split('/').forEach(s=>{ if(/^[A-Za-z]{2}(?:-[A-Za-z]{2,4})?$/.test(s)){ langs.add(s); if(s.includes('-')) langs.add(s.split('-')[0]); } });
		return Array.from(langs);
	}
	function langCandidates(row){
		const cand=new Set(); const meta=(row.language||'').trim(); if(meta){ cand.add(meta); if(meta.includes('-')) cand.add(meta.split('-')[0]); }
		extractLangsFromPath(row.audio_path).forEach(l=>cand.add(l));
		return Array.from(cand);
	}
	function resolveUrlsFor(lang,itemId){
		if(!lang||!itemId) return [];
		return [
			`https://raw.githubusercontent.com/levante-framework/levante_translations/main/audio_files/${encodeURIComponent(lang)}/${encodeURIComponent(itemId)}.mp3`,
			`https://storage.googleapis.com/levante-assets-dev/audio/${encodeURIComponent(lang)}/${encodeURIComponent(itemId)}.mp3`
		];
	}
	async function playAny(urls){ for(const u of urls){ try{ await new Promise((resolve,reject)=>{ const a=new Audio(); a.src=u; a.addEventListener('canplaythrough',()=>{ a.play().then(resolve).catch(reject); },{once:true}); a.addEventListener('error',()=>reject(new Error('play failed')),{once:true}); }); return true; }catch(e){} } return false; }
	
	async function fetchVoiceTag(itemId, lang){
		try{ let r=await fetch(`/api/read-tags?itemId=${encodeURIComponent(itemId)}&langCode=${encodeURIComponent(lang)}`); if(!r.ok){ r=await fetch(`/api/read-tags?itemId=${encodeURIComponent(itemId)}&langCode=${encodeURIComponent(lang)}&source=repo`); } if(!r.ok) return ''; const data=await r.json(); return data?.id3Tags?.voice || data?.id3Tags?.userDefinedText?.find?.(t=>t?.description==='voice')?.value || ''; }catch{ return ''; }
	}
	async function getVoiceNameForRow(row){ const id=stripExt(base(row.audio_path||'')); for(const L of langCandidates(row)){ const v=await fetchVoiceTag(id,L); if(v) return v; } return ''; }
	
	async function findVoiceIdByName(voiceName){ if(!voiceName) return ''; const sel=document.getElementById('elevenlabsVoice'); if(sel){ for(let i=0;i<sel.options.length;i++){ const txt=(sel.options[i].text||'').trim().toLowerCase(); if(txt===voiceName.trim().toLowerCase()) return sel.options[i].value; } for(let i=0;i<sel.options.length;i++){ const txt=(sel.options[i].text||'').trim().toLowerCase(); if(txt.includes(voiceName.trim().toLowerCase())) return sel.options[i].value; } } try{ const creds=getCredentials(); const key=creds.elevenlabs_api_key||creds.elevenlabsApiKey; if(!key) return ''; const resp=await fetch('/api/elevenlabs-proxy',{headers:{'X-API-KEY':key}}); const data=await resp.json(); const list=data?.voices||[]; let exact=list.find(v=>(v.name||'').trim().toLowerCase()===voiceName.trim().toLowerCase()); if(exact) return exact.voice_id||''; let partial=list.find(v=>(v.name||'').toLowerCase().includes(voiceName.trim().toLowerCase())); return partial?.voice_id||''; }catch{ return ''; } }
	
	async function regenerateElevenLabs(text, preferredVoiceId, options){ const creds=getCredentials(); const key=creds.elevenlabs_api_key||creds.elevenlabsApiKey; if(!key) throw new Error('Missing ElevenLabs API key.'); let voiceId=preferredVoiceId||document.getElementById('elevenlabsVoice')?.value||''; if(!voiceId) throw new Error('No voice selected.'); const payload={ text, model_id:'eleven_monolingual_v1', voice_settings:{ stability:0.5, similarity_boost:0.75 } };
		// Apply options
		if(options && typeof options.audio_length==='number') payload.audio_length=options.audio_length;
		if(options && typeof options.style==='number') payload.voice_settings.style=options.style;
		const resp=await fetch(`/api/elevenlabs-proxy?voice_id=${encodeURIComponent(voiceId)}`,{ method:'POST', headers:{'Content-Type':'application/json','X-API-KEY':key}, body:JSON.stringify(payload)}); if(!resp.ok) throw new Error(`ElevenLabs error: ${resp.status}`); const blob=await resp.blob(); const url=URL.createObjectURL(blob); const audio=new Audio(url); await new Promise((resolve,reject)=>{ audio.addEventListener('canplaythrough',()=>{ audio.play().then(resolve).catch(reject); },{once:true}); audio.addEventListener('error',()=>reject(new Error('regen play failed')),{once:true}); }); return { blob, url, voiceId }; }
	
	function blobToDataUrl(blob){ return new Promise((resolve,reject)=>{ const fr=new FileReader(); fr.onload=()=>resolve(fr.result); fr.onerror=reject; fr.readAsDataURL(blob); }); }
	
	function createVm(){
		return createApp({
			setup(){
				const files=ref([]), selectedFile=ref(''), loading=ref(false), error=ref('');
				const results=ref([]), sortKey=ref('similarity'), sortAsc=ref(false);
				const displayLang=ref(''), voiceName=ref('');
				const lastGen=ref({}); // itemId -> { audioBlob, audioUrl, voiceId, voiceName }
				const regenOpenId=ref('');
				const decorated=computed(()=>results.value.map(r=>({ ...r, filename: base(r.audio_path||'') })));
				const sortedRows=computed(()=>{ const rows=[...decorated.value]; const k=sortKey.value; rows.sort((a,b)=>{ if(k==='filename') return (a.filename||'').localeCompare(b.filename||''); if(k==='similarity') return ((a.basic_metrics||{}).similarity_ratio||0)-((b.basic_metrics||{}).similarity_ratio||0); return 0; }); return sortAsc.value?rows:rows.reverse(); });
				
				async function loadFiles(){ try{ const r=await fetch('/api/list-validation-files'); const d=await r.json(); files.value=(d.files||[]).sort().reverse(); if(!selectedFile.value&&files.value.length) selectedFile.value=files.value[0]; }catch(e){ error.value=String(e); } }
				async function loadSelected(){ if(!selectedFile.value) return; loading.value=true; error.value=''; try{ const r=await fetch(`/api/get-validation-file?name=${encodeURIComponent(selectedFile.value)}`); const d=await r.json(); results.value=Array.isArray(d)?d:[d]; const langs=new Set(results.value.map(x=>x.language).filter(Boolean)); displayLang.value=langs.size?Array.from(langs).join(', '):''; if(results.value.length){ const first=results.value[0]; voiceName.value=await getVoiceNameForRow(first); } }catch(e){ error.value=String(e); } finally{ loading.value=false; } }
				function setSort(k){ if(sortKey.value===k) sortAsc.value=!sortAsc.value; else { sortKey.value=k; sortAsc.value=true; } }
				
				function rowId(r){ return stripExt(base(r.audio_path||'')); }
				function toggleRegen(r){ const id=rowId(r); regenOpenId.value = (regenOpenId.value===id ? '' : id); }
				function closeRegen(){ regenOpenId.value=''; }
				
				async function playRow(r){ const id=rowId(r); for(const L of langCandidates(r)){ const ok=await playAny(resolveUrlsFor(L,id)); if(ok) return; } alert('Could not play existing audio.'); }
				async function regenAndPlay(r, options){ try{ const id=rowId(r); const vName=await getVoiceNameForRow(r); const vId=await findVoiceIdByName(vName); const { blob, url, voiceId }=await regenerateElevenLabs(r.expected_text||'', vId, options); lastGen.value[id]={ audioBlob:blob, audioUrl:url, voiceId, voiceName:vName||voiceName.value||'' }; closeRegen(); }catch(e){ alert(String(e)); } }
				function chooseRegen(r, choice){ const map={ default:{}, speed_0_9:{ audio_length:0.9 }, speed_0_7:{ audio_length:0.7 }, boost_style:{ style:0.2 } }; const opts=map[choice]||{}; return regenAndPlay(r, opts); }
				async function saveRow(r){ try{ const id=rowId(r); const gen=lastGen.value[id]; if(!gen){ alert('Please regenerate first.'); return; } const langs=langCandidates(r); const langCode=langs[0]||(r.language||'').trim()||'en'; let existingVoice=''; for(const L of langs){ existingVoice=await fetchVoiceTag(id,L); if(existingVoice) break; } const voiceTag=gen.voiceName||existingVoice||''; const payload={ audioBase64: await blobToDataUrl(gen.audioBlob), langCode, itemId:id, tags:{ title:id, artist:'Levante Project', album:langCode, service:'ElevenLabs', voice:voiceTag, text:r.expected_text||'', created:new Date().toISOString() } }; const resp=await fetch('/api/save-audio',{ method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}); if(!resp.ok) throw new Error(`Save failed: ${resp.status}`); alert('Saved to bucket successfully.'); }catch(e){ alert(String(e)); } }
				
				onMounted(()=>{ loadFiles(); document.addEventListener('click', ()=>{ closeRegen(); }); });
				return { files, selectedFile, loading, error, results, sortedRows,
					summary: computed(()=>{ const sims=results.value.map(x=>(x.basic_metrics||{}).similarity_ratio).filter(x=>typeof x==='number'); if(!sims.length) return null; const avg=sims.reduce((a,b)=>a+b,0)/sims.length; return { count:sims.length, min:Math.min(...sims), max:Math.max(...sims), avg }; }),
					displayLang, voiceName, loadSelected, setSort, playRow, regenAndPlay, saveRow, lastGen, regenOpenId, toggleRegen, chooseRegen, rowId };
			}
		});
	}
	
	if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>{ createVm().mount('#audio-validation-panel'); });
	else createVm().mount('#audio-validation-panel');
})();
