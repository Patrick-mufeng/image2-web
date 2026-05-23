/**
 * Image2 — Apple 风格 v5
 */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const DOM = {
    statusDot: $('statusDot'), statusText: $('statusText'),
    nav: $('nav'), balanceCard: $('balanceCard'),
    balanceStatus: $('balanceStatus'), balanceToken: $('balanceToken'),
    balanceUsage: $('balanceUsage'), balanceRemain: $('balanceRemain'),
    pageBaseUrl: $('pageBaseUrl'), pageApiKey: $('pageApiKey'),
    pageStatus: $('pageStatus'), pageSaveBtn: $('pageSaveBtn'),
    ratioGrid: $('ratioGrid'), resolutionSelect: $('resolutionSelect'),
    modelSelect: $('modelSelect'), countGroup: $('countGroup'),
    promptInput: $('promptInput'), charCount: $('charCount'),
    multiMode: $('multiMode'), multiHint: $('multiHint'),
    btnGenerate: $('btnGenerate'), btnCancel: $('btnCancel'),
    emptyState: $('emptyState'), genBox: $('genBox'),
    genLog: $('genLog'), genBar: $('genBar'), genBadge: $('genBadge'),
    resultsWrap: $('resultsWrap'), imgGrid: $('imgGrid'), resultsCount: $('resultsCount'),
    historyGrid: $('historyGrid'), historyEmpty: $('historyEmpty'),
    historyPages: $('historyPages'), btnClearHistory: $('btnClearHistory'),
    monLive: $('monLive'), monEmpty: $('monEmpty'), monBody: $('monBody'),
    monReq: $('monReq'), monRes: $('monRes'), monResTag: $('monResTag'),
    tlProcess: $('tlProcess'), tlDone: $('tlDone'),
    toastWrap: $('toastWrap'), lightbox: $('lightbox'), lbImg: $('lbImg'),
    // Image-to-image
    btnModeTxt2Img: $('btnModeTxt2Img'), btnModeImg2Img: $('btnModeImg2Img'),
    img2imgArea: $('img2imgArea'), uploadZone: $('uploadZone'),
    fileInput: $('fileInput'), uploadPreviews: $('uploadPreviews'),
    maskToggle: $('maskToggle'), maskMode: $('maskMode'),
    maskUpload: $('maskUpload'), maskInput: $('maskInput'),
    btnMaskBrowse: $('btnMaskBrowse'), maskName: $('maskName'),
    btnGenLabel: $('btnGenLabel'), btnBrowse: $('btnBrowse'),
  };

  const S = {
    tab: 0,
    aspectRatio: '1:1', megapixels: '1', model: 'gpt-image-2',
    numOutputs: 1, prompt: '', models: [],
    apiConfigured: false, userApiKey: '', userBaseUrl: '',
    isGenerating: false, multiMode: false,
    mode: 'txt2img',  // 'txt2img' | 'img2img'
    uploadedFiles: [], // [{file, dataUrl}]
    maskFile: null,
    historyPage: 1, historyLimit: 12, historyTotal: 0, historyRecords: [],
  };

  let _pollTimer = null, _currentTaskId = null, _knownLogLen = 0;

  const esc = s => { const d = document.createElement('div'); d.textContent = s||''; return d.innerHTML; };
  const fmtTime = iso => { if (!iso) return ''; try { return new Date(iso).toLocaleString('zh-CN'); } catch(e) { return iso; } };

  function toast(msg, type) {
    const t = document.createElement('div');
    t.className = 'toast ' + (type==='success'?'ok':type==='error'?'err':'info');
    t.textContent = msg;
    DOM.toastWrap.appendChild(t);
    setTimeout(() => { t.classList.add('out'); t.addEventListener('animationend', () => t.remove()); }, 3500);
  }

  async function api(method, url, body) {
    try {
      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(url, opts);
      return await r.json();
    } catch(e) { return { success: false, error: '网络错误: ' + e.message }; }
  }

  // ── Nav ──
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      const pane = document.getElementById('tab' + tab);
      if (pane) pane.classList.add('active');
      S.tab = +tab;
    });
  });

  function switchTab(tab) {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', +b.dataset.tab === tab));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', +p.id.replace('tab','') === tab));
    S.tab = tab;
  }

  // ── Status ──
  function updStatus() {
    DOM.statusDot.className = 'hdr-dot ' + (S.apiConfigured ? 'on' : 'off');
    DOM.statusText.textContent = S.apiConfigured ? '已连接' : '未配置';
  }

  // ── Tab 0: Settings ──
  function renderSettings() {
    DOM.pageStatus.innerHTML = S.apiConfigured
      ? '<span class="bdg ok">✅ 已连接</span>'
      : '<span class="bdg miss">❌ 未配置</span>';
    DOM.pageBaseUrl.value = S.userBaseUrl || 'https://yunwu.ai';
    DOM.pageApiKey.value = S.userApiKey || '';
  }
  DOM.pageSaveBtn.addEventListener('click', async () => {
    const k = DOM.pageApiKey.value.trim(), u = DOM.pageBaseUrl.value.trim();
    const r = await api('POST', '/api/config/settings', { api_key: k, base_url: u });
    if (r.success) {
      S.userApiKey = k; S.userBaseUrl = u;
      S.apiConfigured = !!k;
      S.apiKeyChanged = true;
      updStatus(); renderSettings();
      toast('设置已保存', 'success');
      // 保存后自动查询余额
      if (k) queryBalance();
    } else { toast('保存失败: ' + (r.error || '未知'), 'error'); }
  });

  // ── Balance Query ──
  async function queryBalance() {
    DOM.balanceCard.style.display = '';
    DOM.balanceStatus.textContent = '查询中...';
    DOM.balanceStatus.className = 'balance-status';
    try {
      const data = await api('GET', '/api/config/balance');
      if (!data.configured) {
        DOM.balanceStatus.textContent = '⏸ 未配置';
        DOM.balanceStatus.className = 'balance-status';
        DOM.balanceToken.textContent = '-';
        DOM.balanceUsage.textContent = '-';
        DOM.balanceRemain.textContent = '-';
        return;
      }
      if (data.error) {
        DOM.balanceStatus.textContent = '❌ ' + data.error;
        DOM.balanceStatus.className = 'balance-status err';
        return;
      }
      DOM.balanceStatus.textContent = '✅ 已更新';
      DOM.balanceStatus.className = 'balance-status ok';
      DOM.balanceToken.textContent = data.token_name || '-';
      DOM.balanceUsage.textContent = '$' + (data.total_usage || 0);
      DOM.balanceRemain.textContent = data.remaining || '-';
    } catch(e) {
      DOM.balanceStatus.textContent = '❌ 查询失败';
      DOM.balanceStatus.className = 'balance-status err';
    }
  }

  // Auto-query balance when switching to tab 0
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      if (tab === '0' && S.apiConfigured) {
        queryBalance();
      }
    });
  });

  // ── Tab 1: Ratios ──
  const RATIOS = [{r:'1:1',l:'1:1'},{r:'16:9',l:'16:9'},{r:'9:16',l:'9:16'},{r:'4:3',l:'4:3'},{r:'3:4',l:'3:4'}];
  function renderRatios() {
    DOM.ratioGrid.innerHTML = '';
    RATIOS.forEach(r => {
      const b = document.createElement('button');
      b.className = 'p-btn' + (r.r === S.aspectRatio ? ' active' : '');
      b.dataset.ratio = r.r; b.textContent = r.l;
      b.addEventListener('click', () => {
        S.aspectRatio = r.r;
        DOM.ratioGrid.querySelectorAll('.p-btn').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
      });
      DOM.ratioGrid.appendChild(b);
    });
  }

  // ── Tab 1: Models ──
  function renderModels() {
    DOM.modelSelect.innerHTML = '';
    if (!S.models.length) {
      const o = document.createElement('option'); o.value = 'gpt-image-2'; o.textContent = 'GPT Image 2';
      DOM.modelSelect.appendChild(o); return;
    }
    const groups = {};
    S.models.forEach(m => { const g = m.group||'其他'; if(!groups[g]) groups[g]=[]; groups[g].push(m); });
    Object.keys(groups).forEach(gName => {
      const grp = document.createElement('optgroup'); grp.label = gName;
      groups[gName].forEach(m => {
        const o = document.createElement('option'); o.value = m.value; o.textContent = m.label;
        if (m.value === S.model) o.selected = true;
        grp.appendChild(o);
      });
      DOM.modelSelect.appendChild(grp);
    });
  }

  // ── Tab 1: Helpers ──
  function getPrompts() { if (!S.multiMode) return null; return S.prompt.split('\n').map(s=>s.trim()).filter(Boolean); }
  function updMultiHint() {
    if (!DOM.multiHint) return;
    if (!S.multiMode) { DOM.multiHint.textContent = '每行各一张'; return; }
    const lines = getPrompts();
    DOM.multiHint.textContent = (lines && lines.length > 1) ? lines.length + ' 个' : '每行各一张';
  }
  function updBtn() {
    if (S.mode === 'img2img') {
      DOM.btnGenerate.disabled = !S.prompt.trim() || S.isGenerating || !S.uploadedFiles.length;
    } else {
      DOM.btnGenerate.disabled = !S.prompt.trim() || S.isGenerating;
    }
  }

  // ── Tab 1: Mode Toggle ──
  function switchMode(mode) {
    S.mode = mode;
    document.querySelectorAll('.gm-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    DOM.img2imgArea.style.display = mode === 'img2img' ? '' : 'none';
    DOM.btnGenLabel.textContent = mode === 'img2img' ? '图生图' : '生成';

    // Disable multi-mode in img2img
    if (mode === 'img2img') {
      DOM.multiMode.checked = false;
      S.multiMode = false;
      DOM.multiMode.disabled = true;
    } else {
      DOM.multiMode.disabled = false;
    }
    updBtn();
  }

  if (DOM.btnModeTxt2Img) {
    DOM.btnModeTxt2Img.addEventListener('click', () => switchMode('txt2img'));
  }
  if (DOM.btnModeImg2Img) {
    DOM.btnModeImg2Img.addEventListener('click', () => switchMode('img2img'));
  }

  // ── Tab 1: Image Upload ──
  function handleFiles(files) {
    const validTypes = ['image/png', 'image/jpeg', 'image/webp'];
    const maxSize = 50 * 1024 * 1024; // 50MB total

    let added = 0;
    for (const file of files) {
      if (!validTypes.includes(file.type) && !file.name.match(/\.(png|jpe?g|webp)$/i)) continue;
      if (S.uploadedFiles.length >= 16) {
        toast('最多 16 张图片', 'error');
        break;
      }
      // Check total size
      const totalSize = S.uploadedFiles.reduce((s, f) => s + f.file.size, 0) + file.size;
      if (totalSize > maxSize) {
        toast('图片总大小超过 50MB', 'error');
        break;
      }
      S.uploadedFiles.push({ file, dataUrl: URL.createObjectURL(file) });
      added++;
    }
    if (added) {
      renderPreviews();
      updBtn();
      toast('已添加 ' + added + ' 张图片', 'success');
    }
  }

  function removeFile(index) {
    const item = S.uploadedFiles[index];
    if (item && item.dataUrl) URL.revokeObjectURL(item.dataUrl);
    S.uploadedFiles.splice(index, 1);
    renderPreviews();
    updBtn();
  }

  function renderPreviews() {
    DOM.uploadPreviews.innerHTML = '';
    if (!S.uploadedFiles.length) {
      DOM.uploadPreviews.style.display = 'none';
      return;
    }
    DOM.uploadPreviews.style.display = 'flex';
    S.uploadedFiles.forEach((item, i) => {
      const div = document.createElement('div');
      div.className = 'up-item';
      div.innerHTML = '<img src="' + item.dataUrl + '" alt=""><button class="up-del" data-i="' + i + '">✕</button>';
      div.querySelector('.up-del').addEventListener('click', () => removeFile(i));
      DOM.uploadPreviews.appendChild(div);
    });
  }

  // Drag & Drop
  if (DOM.uploadZone) {
    DOM.uploadZone.addEventListener('dragover', e => {
      e.preventDefault();
      DOM.uploadZone.classList.add('drag-over');
    });
    DOM.uploadZone.addEventListener('dragleave', () => {
      DOM.uploadZone.classList.remove('drag-over');
    });
    DOM.uploadZone.addEventListener('drop', e => {
      e.preventDefault();
      DOM.uploadZone.classList.remove('drag-over');
      if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
    });
  }

  // Browse button
  if (DOM.btnBrowse) {
    DOM.btnBrowse.addEventListener('click', () => DOM.fileInput.click());
  }
  if (DOM.fileInput) {
    DOM.fileInput.addEventListener('change', () => {
      if (DOM.fileInput.files.length) handleFiles(DOM.fileInput.files);
      DOM.fileInput.value = '';
    });
  }

  // Mask toggle
  if (DOM.maskMode) {
    DOM.maskMode.addEventListener('change', () => {
      DOM.maskUpload.style.display = DOM.maskMode.checked ? '' : 'none';
      if (!DOM.maskMode.checked) { S.maskFile = null; DOM.maskName.textContent = '未选择'; }
    });
  }
  if (DOM.btnMaskBrowse) {
    DOM.btnMaskBrowse.addEventListener('click', () => DOM.maskInput.click());
  }
  if (DOM.maskInput) {
    DOM.maskInput.addEventListener('change', () => {
      if (DOM.maskInput.files.length) {
        S.maskFile = DOM.maskInput.files[0];
        DOM.maskName.textContent = S.maskFile.name;
      }
    });
  }

  // ── Tab 1: Log ──
  function log(text, cls) {
    cls = cls || 'l';
    const line = document.createElement('div'); line.className = cls; line.textContent = text;
    DOM.genLog.appendChild(line); DOM.genLog.scrollTop = DOM.genLog.scrollHeight;
  }

  // ── Tab 1: Images ──
  function renderImgs(images) {
    DOM.resultsWrap.classList.add('show');
    DOM.resultsCount.textContent = images.length + ' 张';
    DOM.imgGrid.innerHTML = '';
    DOM.imgGrid.setAttribute('data-c', images.length);
    images.forEach((img, i) => {
      const src = img.local_path || img.url || '';
      const card = document.createElement('div'); card.className = 'img-card';
      card.style.animationDelay = (i*0.08)+'s';
      let h = '<img src="'+esc(src)+'" alt="" loading="eager" onclick="window._lb(\''+esc(src)+'\')" onload="this.parentNode.querySelector(\'.img-size\').textContent=this.naturalWidth+\'×\'+this.naturalHeight">';
      h += '<span class="img-size">...</span>';
      h += '<div class="img-card-body"><div class="img-card-actions">';
      h += '<a href="'+esc(src)+'" download="img_'+(i+1)+'.png" class="btn btn-p" style="text-decoration:none">📥 下载</a>';
      h += '<button class="btn btn-s" onclick="window._cpy(\''+esc(src)+'\')">🔗 复制</button></div>';
      if (img.revised_prompt) h += '<div class="revised">💡 '+esc(img.revised_prompt)+'</div>';
      h += '</div>'; card.innerHTML = h; DOM.imgGrid.appendChild(card);
    });
    DOM.resultsWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  window._lb = function(src) { DOM.lightbox.style.display='flex'; DOM.lbImg.src=src; };
  window._cpy = async function(url) {
    try { await navigator.clipboard.writeText(url.startsWith('http')?url:location.origin+url); toast('已复制','success'); }
    catch(e) { toast('复制失败','error'); }
  };

  // ── Tab 3: Monitor ──
  function updateMonitor(reqData, resData) {
    DOM.monEmpty.style.display='none'; DOM.monBody.style.display='flex';
    DOM.btnClearMonitor.style.display='inline-flex';
    if (reqData) { S.lastReqData=reqData; DOM.monReq.textContent=JSON.stringify(reqData,null,2); }
    if (resData) { S.lastResData=resData; DOM.monRes.textContent=JSON.stringify(resData,null,2); }
    DOM.monLive.className='mon-live active'; DOM.monLive.innerHTML='<span class="pulse">●</span> 实时';
    DOM.monResTag.className='mon-tag pending'; DOM.monResTag.textContent='⏳ 接收中';
    DOM.tlProcess.classList.add('active');
  }
  function finalizeMonitor(ok) {
    if (ok) {
      DOM.monLive.className='mon-live'; DOM.monLive.innerHTML='● 请求完成';
      DOM.monResTag.className='mon-tag live'; DOM.monResTag.textContent='✅ RECEIVED';
      DOM.tlProcess.classList.remove('active'); DOM.tlProcess.classList.add('done');
      DOM.tlDone.classList.add('done');
      setTimeout(() => { DOM.tlProcess.classList.remove('done'); DOM.tlDone.classList.remove('done'); }, 3000);
    } else {
      DOM.monLive.className='mon-live'; DOM.monLive.innerHTML='● 请求失败';
      DOM.monResTag.className='mon-tag'; DOM.monResTag.textContent='❌ FAILED';
    }
  }

  // ── Generate ──
  async function genOne(prompt, idx, total) {
    log('  ['+idx+'/'+total+'] 📤 '+prompt.slice(0,50)+(prompt.length>50?'…':''),'l');
    const resp = await api('POST','/api/generate',{prompt,aspect_ratio:S.aspectRatio,megapixels:S.megapixels,num_outputs:1,model:S.model});
    if (resp.success && resp.images && resp.images.length) { log('  ['+idx+'/'+total+'] ✅ 完成','ok'); return {images:resp.images,request:resp.request_data,response:resp.response_data}; }
    log('  ['+idx+'/'+total+'] ❌ '+(resp.error||'失败'),'err');
    return {images:[],error:resp.error};
  }

  async function apiFormData(url, formData) {
    try {
      const r = await fetch(url, { method: 'POST', body: formData });
      return await r.json();
    } catch(e) { return { success: false, error: '网络错误: ' + e.message }; }
  }

  async function generateImage() {
    if (!S.prompt.trim() || S.isGenerating) return;
    if (!S.apiConfigured) { toast('请先配置 API Key','error'); switchTab(0); return; }

    // Image-to-image mode
    if (S.mode === 'img2img') {
      return await generateEdit();
    }

    const prompts = S.multiMode ? getPrompts() : null;
    const isMulti = prompts && prompts.length > 1;
    S.isGenerating = true; stopPoll();
    DOM.btnGenerate.style.display='none'; DOM.btnCancel.style.display='inline-flex';
    DOM.emptyState.style.display='none'; DOM.genBox.style.display='';
    DOM.resultsWrap.classList.remove('show'); DOM.genLog.innerHTML='';
    DOM.genBar.className='g-fill idet'; DOM.genBadge.textContent='请求中'; DOM.genBadge.className='g-bdg';
    updBtn();
    DOM.monEmpty.style.display='none'; DOM.monBody.style.display='flex';
    DOM.monReq.textContent='等待请求…'; DOM.monRes.textContent='等待响应…';
    log(isMulti?'🚀 批量生成 '+prompts.length+' 张不同图片':'🚀 开始生成','hl');
    log(S.aspectRatio+' · '+S.megapixels+'MP · '+S.model,'l');
    S.lastPrompt = S.prompt;
    const t0 = Date.now(); switchTab(1);
    DOM.btnRetry.style.display = 'none';
    DOM.btnDownloadAll.style.display = 'none';

    try {
      if (isMulti) {
        const allImages=[]; const n=prompts.length; DOM.genBadge.textContent='0/'+n;
        for (let i=0; i<n; i++) {
          DOM.genBadge.textContent=(i+1)+'/'+n;
          const result = await genOne(prompts[i],i+1,n);
          if (result.images) allImages.push(...result.images);
        }
        const sec=((Date.now()-t0)/1000).toFixed(1);
        if (allImages.length) {
          DOM.genBadge.textContent='✅ '+allImages.length+' 张'; DOM.genBadge.className='g-bdg done';
          DOM.genBar.className='g-fill'; DOM.genBar.style.width='100%';
          log('✅ 全部完成! 共 '+allImages.length+' 张, '+sec+'s','ok');
          renderImgs(allImages); toast('生成 '+allImages.length+' 张','success');
          DOM.btnDownloadAll.style.display = 'inline-flex';
          S.historyPage=1; loadHistory();
        } else {
          DOM.genBadge.textContent='❌ 全部失败'; DOM.genBadge.className='g-bdg fail';
          log('❌ 全部失败','err'); toast('全部失败','error');
          DOM.btnRetry.style.display = 'inline-flex';
        }
        finalizeMonitor(allImages.length>0); finishGen(); return;
      }

      const resp = await api('POST','/api/generate',{prompt:S.prompt,aspect_ratio:S.aspectRatio,megapixels:S.megapixels,num_outputs:S.numOutputs,model:S.model});
      updateMonitor(resp.request_data||{prompt:S.prompt,model:S.model},resp.response_data||null);

      if (!resp.success) {
        DOM.genBadge.textContent='❌ 失败'; DOM.genBadge.className='g-bdg fail';
        log('❌ '+(resp.error||'失败'),'err'); toast(resp.error||'失败','error');
        DOM.btnRetry.style.display = 'inline-flex';
        finalizeMonitor(false); finishGen(); return;
      }

      if (resp.logs) resp.logs.split('\n').filter(Boolean).forEach(l=>log(l,'l'));
      _knownLogLen=resp.logs?resp.logs.length:0; _currentTaskId=resp.task_id;

      if (resp.images && resp.images.length) {
        DOM.genBadge.textContent='✅ 完成'; DOM.genBadge.className='g-bdg done';
        DOM.genBar.className='g-fill'; DOM.genBar.style.width='100%';
        const sec=((Date.now()-t0)/1000).toFixed(1);
        log('✅ 成功! '+sec+'s','ok'); renderImgs(resp.images);
        toast('生成 '+resp.images.length+' 张','success');
        DOM.btnDownloadAll.style.display = 'inline-flex';
        S.historyPage=1; loadHistory(); finalizeMonitor(true); finishGen(); return;
      }

      log('📡 实时跟踪...','hl'); DOM.genBadge.textContent='⏳ 处理中'; startPoll(t0);
    } catch(e) { log('❌ '+e.message,'err'); toast('异常: '+e.message,'error'); finalizeMonitor(false); finishGen(); }
  }

  // ── Image-to-Image ──
  function getEditSize() {
    // Map ratio+megapixels to size string (same as backend)
    const map = {
      '1:1_1': '1024x1024', '1:1_2': '2048x2048', '1:1_4': '4096x4096',
      '16:9_1': '1280x720', '16:9_2': '2560x1440', '16:9_4': '3840x2160',
      '9:16_1': '720x1280', '9:16_2': '1440x2560', '9:16_4': '2160x3840',
      '4:3_1': '1152x864', '4:3_2': '2048x1536', '4:3_4': '4096x3072',
      '3:4_1': '864x1152', '3:4_2': '1536x2048', '3:4_4': '3072x4096',
    };
    return map[S.aspectRatio + '_' + S.megapixels] || '1024x1024';
  }

  async function generateEdit() {
    if (!S.prompt.trim() || S.isGenerating || !S.uploadedFiles.length) return;
    if (!S.apiConfigured) { toast('请先配置 API Key','error'); switchTab(0); return; }

    S.isGenerating = true; stopPoll();
    DOM.btnGenerate.style.display='none'; DOM.btnCancel.style.display='inline-flex';
    DOM.emptyState.style.display='none'; DOM.genBox.style.display='';
    DOM.resultsWrap.classList.remove('show'); DOM.genLog.innerHTML='';
    DOM.genBar.className='g-fill idet'; DOM.genBadge.textContent='上传中'; DOM.genBadge.className='g-bdg';
    updBtn();
    DOM.monEmpty.style.display='none'; DOM.monBody.style.display='flex';
    DOM.monReq.textContent='等待请求…'; DOM.monRes.textContent='等待响应…';
    DOM.btnRetry.style.display = 'none';
    DOM.btnDownloadAll.style.display = 'none';

    const editSize = getEditSize();
    log('🖼️ 开始图生图编辑','hl');
    log(S.model + ' · ' + editSize + ' · ' + S.uploadedFiles.length + ' 张图片','l');
    S.lastPrompt = S.prompt;
    const t0 = Date.now();
    switchTab(1);

    try {
      // Build FormData
      const formData = new FormData();
      formData.append('prompt', S.prompt);
      formData.append('model', S.model);
      formData.append('size', editSize);
      formData.append('n', String(S.numOutputs));
      formData.append('quality', 'auto');
      formData.append('background', 'auto');
      for (const item of S.uploadedFiles) {
        formData.append('images', item.file);
      }
      if (S.maskFile) {
        formData.append('mask', S.maskFile);
      }

      log('📤 上传 ' + S.uploadedFiles.length + ' 张图片...','l');
      DOM.genBadge.textContent='上传中';

      // Update monitor with request preview
      const reqPreview = { prompt: S.prompt.slice(0,80), model: S.model, size: editSize, n: S.numOutputs, images: S.uploadedFiles.length };
      DOM.monReq.textContent = JSON.stringify(reqPreview, null, 2);
      DOM.monRes.textContent = '等待响应…';
      DOM.monLive.className = 'mon-live active';
      DOM.monResTag.className = 'mon-tag pending';
      DOM.monResTag.textContent = '⏳ 处理中';

      const resp = await apiFormData('/api/edits', formData);

      // Update monitor with response
      DOM.monRes.textContent = JSON.stringify(resp.response_data || resp, null, 2);
      DOM.monResTag.textContent = resp.success ? '✅ 完成' : '❌ 失败';
      DOM.monLive.className = 'mon-live';
      DOM.monLive.innerHTML = resp.success ? '● 请求完成' : '● 请求失败';
      document.querySelectorAll('.tl-i').forEach(t => t.classList.add('done'));

      if (resp.logs) resp.logs.split('\n').filter(Boolean).forEach(l => log(l, 'l'));

      if (resp.success && resp.images && resp.images.length) {
        DOM.genBadge.textContent = '✅ 完成';
        DOM.genBadge.className = 'g-bdg done';
        DOM.genBar.className = 'g-fill';
        DOM.genBar.style.width = '100%';
        const sec = ((Date.now()-t0)/1000).toFixed(1);
        log('✅ 成功! ' + sec + 's', 'ok');
        renderImgs(resp.images);
        toast('生成 ' + resp.images.length + ' 张', 'success');
        DOM.btnDownloadAll.style.display = 'inline-flex';
        S.historyPage = 1; loadHistory();
      } else {
        DOM.genBadge.textContent = '❌ 失败';
        DOM.genBadge.className = 'g-bdg fail';
        log('❌ ' + (resp.error || '失败'), 'err');
        toast(resp.error || '图生图失败', 'error');
        DOM.btnRetry.style.display = 'inline-flex';
      }
    } catch(e) {
      log('❌ ' + e.message, 'err');
      toast('异常: ' + e.message, 'error');
    } finally {
      finishGen();
    }
  }

  function startPoll(t0) {
    if (!_currentTaskId) { finishGen(); return; }
    _pollTimer = setTimeout(async () => {
      try {
        const data = await api('GET','/api/task/'+_currentTaskId);
        const full = data.logs||'';
        if (full.length>_knownLogLen) { full.substring(_knownLogLen).split('\n').filter(Boolean).forEach(l=>log(l,'l')); _knownLogLen=full.length; }
        DOM.genBadge.textContent='⏳ '+(data.status||'…');
        // 实时更新监控面板
        const elapsed = ((Date.now()-t0)/1000).toFixed(1);
        DOM.monLive.className='mon-live active';
        DOM.monLive.innerHTML='<span class="pulse">●</span> ' + elapsed + 's';
        if (data.response_data) DOM.monRes.textContent=JSON.stringify(data.response_data,null,2);
        if (data.logs) DOM.monResTag.textContent='⏳ '+(data.status||'…');
        if (data._done) {
          const sec=((Date.now()-t0)/1000).toFixed(1);
          if (data.status==='succeeded') {
            DOM.genBadge.textContent='✅ 完成'; DOM.genBadge.className='g-bdg done';
            DOM.genBar.className='g-fill'; DOM.genBar.style.width='100%';
            log('✅ 成功! '+sec+'s','ok');
            updateMonitor(data.request_data,data.response_data);
            const local=data.local_images||[],urls=data.output||[],imgs=[];
            if (local.length) local.forEach((p,i)=>imgs.push({local_path:p,url:urls[i]||''}));
            else if (urls.length) urls.forEach(u=>imgs.push({url:u}));
            if (imgs.length) { renderImgs(imgs); toast('生成 '+imgs.length+' 张','success'); DOM.btnDownloadAll.style.display='inline-flex'; }
            S.historyPage=1; loadHistory(); finalizeMonitor(true);
          } else {
            DOM.genBadge.textContent='❌ 失败'; DOM.genBadge.className='g-bdg fail';
            log('❌ '+(data.error||data.status||'失败'),'err');
            updateMonitor(data.request_data,data.response_data);
            toast(data.error||'失败','error'); finalizeMonitor(false);
          }
          finishGen(); return;
        }
        startPoll(t0);
      } catch(e) { log('⚠️ '+e.message,'warn'); startPoll(t0); }
    }, 600);
  }

  function stopPoll() { if(_pollTimer){clearTimeout(_pollTimer);_pollTimer=null;} _currentTaskId=null; _knownLogLen=0; }
  function finishGen() { S.isGenerating=false; stopPoll(); DOM.btnGenerate.style.display=''; DOM.btnCancel.style.display='none'; updBtn(); }
  function cancelGen() { S.isGenerating=false; stopPoll(); DOM.btnGenerate.style.display=''; DOM.btnCancel.style.display='none'; DOM.genBox.style.display='none'; if(!DOM.imgGrid.children.length) DOM.emptyState.style.display=''; updBtn(); log('⏹ 已取消','warn'); }

  // ── History ──
  async function loadHistory() {
    const d = await api('GET','/api/history?page='+S.historyPage+'&limit='+S.historyLimit);
    if (!d||!d.records||!d.records.length) { DOM.historyGrid.innerHTML=''; DOM.historyEmpty.style.display=''; DOM.historyPages.style.display='none'; S.historyTotal=0; return; }
    S.historyTotal=d.total; DOM.historyEmpty.style.display='none'; S.historyRecords=d.records;
    let html='';
    d.records.forEach((rec,i)=>{
      const img=rec.images&&rec.images[0]; const src=img?(img.local_path||img.url||''):''; const date=fmtTime(rec.created_at);
      html+='<div class="hist-card" style="animation-delay:'+(i*0.04)+'s" onclick="window._loadHist('+i+')">';
      html+=src?'<img src="'+esc(src)+'" alt="" loading="lazy">':'<div class="skel"></div>';
      html+='<div class="hist-card-info"><div class="hist-card-meta">'+esc(rec.aspect_ratio||rec.model||'')+'</div>';
      html+='<div class="hist-card-prompt">'+esc(rec.prompt||'')+'</div><div class="hist-card-date">'+date+'</div></div></div>';
    });
    DOM.historyGrid.innerHTML=html;
    const pages=Math.ceil(S.historyTotal/S.historyLimit);
    if (pages>1) {
      DOM.historyPages.style.display='flex'; let h='';
      if (S.historyPage>1) h+='<button class="btn btn-s btn-sm" onclick="window._goPage('+(S.historyPage-1)+')">←</button>';
      h+='<span>'+S.historyPage+'/'+pages+'</span>';
      if (S.historyPage<pages) h+='<button class="btn btn-s btn-sm" onclick="window._goPage('+(S.historyPage+1)+')">→</button>';
      DOM.historyPages.innerHTML=h;
    } else DOM.historyPages.style.display='none';
  }
  window._loadHist=function(i){
    const rec=S.historyRecords[i];if(!rec)return;
    // Show detail modal
    const modal=document.getElementById('histModal');
    const imgDiv=document.getElementById('histDetailImg');
    const infoDiv=document.getElementById('histDetailInfo');
    if(!modal||!imgDiv||!infoDiv)return;

    // Images
    const imgs=rec.images||[];
    imgDiv.innerHTML='';
    imgDiv.className='hist-d-img'+(imgs.length<=1?' single':'');
    imgs.forEach(img=>{
      const src=img.local_path||img.url||'';
      if(src){
        const el=document.createElement('img');
        el.src=src;el.alt='';el.loading='lazy';
        el.onclick=function(){window._lb(src);};
        imgDiv.appendChild(el);
      }
    });

    // Params info
    const modelLabels={}; S.models.forEach(m=>{modelLabels[m.value]=m.label;});
    const modelLabel=modelLabels[rec.model]||rec.model||'-';
    const sizeLabel=rec.size||rec.aspect_ratio?rec.aspect_ratio+(rec.megapixels?' '+rec.megapixels+'MP':''):'-';
    const date=fmtTime(rec.created_at);
    const prompt=rec.prompt||'';
    const n=rec.num_outputs||'1';

    infoDiv.innerHTML=
      '<div class="row"><span class="lbl">模型</span><span class="val">'+esc(modelLabel)+'</span></div>'+
      '<div class="row"><span class="lbl">比例</span><span class="val">'+esc(sizeLabel)+'</span></div>'+
      '<div class="row"><span class="lbl">数量</span><span class="val">'+n+' 张</span></div>'+
      '<div class="row"><span class="lbl">时间</span><span class="val">'+esc(date)+'</span></div>'+
      '<div class="row"><span class="lbl">提示词</span><span class="val prompt">'+esc(prompt)+'</span></div>';

    // Store current record for modify button
    window._currentHistRec=rec;
    modal.style.display='flex';
  };
  window._goPage=function(p){if(p<1||p>Math.ceil(S.historyTotal/S.historyLimit))return;S.historyPage=p;loadHistory();};

  // ── Theme Toggle ──
  function setTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : '');
    document.getElementById('themeIcon').textContent = dark ? '☀️' : '🌙';
    localStorage.setItem('img2-theme', dark ? 'dark' : 'light');
  }
  DOM.btnTheme = document.getElementById('btnTheme');
  DOM.themeIcon = document.getElementById('themeIcon');
  if (DOM.btnTheme) {
    const saved = localStorage.getItem('img2-theme');
    if (saved === 'dark') setTheme(true);
    DOM.btnTheme.addEventListener('click', () => {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      setTheme(!isDark);
    });
  }

  // ── Esc close lightbox ──
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { DOM.lightbox.style.display = 'none'; }
  });

  // ── Download All ──
  DOM.btnDownloadAll = document.getElementById('btnDownloadAll');
  if (DOM.btnDownloadAll) {
    DOM.btnDownloadAll.addEventListener('click', async () => {
      const imgs = DOM.imgGrid.querySelectorAll('.img-card img');
      if (!imgs.length) return;
      for (let i = 0; i < imgs.length; i++) {
        const src = imgs[i].src;
        try {
          const resp = await fetch(src);
          const blob = await resp.blob();
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = 'image2_' + (i+1) + '.' + (blob.type.includes('png') ? 'png' : 'jpg');
          a.click();
          URL.revokeObjectURL(a.href);
        } catch(e) { console.warn('下载失败:', i+1, e); }
      }
      toast('已下载 ' + imgs.length + ' 张图片', 'success');
    });
  }

  // ── Retry ──
  DOM.btnRetry = document.getElementById('btnRetry');
  if (DOM.btnRetry) {
    DOM.btnRetry.addEventListener('click', () => {
      S.isGenerating = false; // reset
      generateImage();
    });
  }

  // ── Monitor Clear ──
  DOM.btnClearMonitor = document.getElementById('btnClearMonitor');
  if (DOM.btnClearMonitor) {
    DOM.btnClearMonitor.addEventListener('click', () => {
      DOM.monBody.style.display = 'none';
      DOM.monEmpty.style.display = '';
      DOM.monReq.textContent = '暂无';
      DOM.monRes.textContent = '暂无';
      DOM.monLive.className = 'mon-live';
      DOM.monLive.innerHTML = '● 等待请求';
      DOM.monResTag.className = 'mon-tag';
      DOM.monResTag.textContent = 'RECEIVED';
      DOM.btnClearMonitor.style.display = 'none';
      // Reset timeline
      document.querySelectorAll('.tl-i').forEach(t => { t.classList.remove('active','done'); });
      document.querySelector('.tl-i').classList.add('active');
    });
  }

  // ── Events ──
  DOM.resolutionSelect.addEventListener('change',()=>{S.megapixels=DOM.resolutionSelect.value;});
  DOM.modelSelect.addEventListener('change',()=>{S.model=DOM.modelSelect.value;});
  DOM.countGroup.addEventListener('click',e=>{const b=e.target.closest('.p-btn');if(!b)return;S.numOutputs=+b.dataset.count;DOM.countGroup.querySelectorAll('.p-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');});
  if(DOM.multiMode){DOM.multiMode.addEventListener('change',()=>{S.multiMode=DOM.multiMode.checked;updMultiHint();});}
  DOM.promptInput.addEventListener('input',()=>{S.prompt=DOM.promptInput.value;DOM.charCount.textContent=S.prompt.length+' / 4000';updMultiHint();updBtn();});
  DOM.promptInput.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();generateImage();}});
  DOM.btnGenerate.addEventListener('click',generateImage);
  DOM.btnCancel.addEventListener('click',cancelGen);
  DOM.btnClearHistory.addEventListener('click',async()=>{if(!confirm('清空所有历史记录？'))return;await api('DELETE','/api/history');S.historyPage=1;loadHistory();toast('已清空','success');});
  DOM.lightbox.addEventListener('click',()=>{DOM.lightbox.style.display='none';});

  // ── History Modal ──
  function closeHistModal(){
    document.getElementById('histModal').style.display='none';
    window._currentHistRec=null;
  }
  const btnCloseHist=document.getElementById('btnCloseHist');
  const btnCloseHist2=document.getElementById('btnCloseHist2');
  const btnHistModify=document.getElementById('btnHistModify');
  if(btnCloseHist) btnCloseHist.addEventListener('click',closeHistModal);
  if(btnCloseHist2) btnCloseHist2.addEventListener('click',closeHistModal);
  if(btnHistModify){
    btnHistModify.addEventListener('click',()=>{
      const rec=window._currentHistRec;
      if(!rec)return;
      closeHistModal();
      // Load params into generation tab
      S.prompt=rec.prompt||'';
      S.model=rec.model||'gpt-image-2';
      S.aspectRatio=rec.aspect_ratio||'1:1';
      S.megapixels=rec.megapixels||'1';
      S.numOutputs=rec.num_outputs||1;
      // Update UI
      DOM.promptInput.value=S.prompt;
      DOM.charCount.textContent=S.prompt.length+' / 4000';
      DOM.modelSelect.value=S.model;
      DOM.resolutionSelect.value=S.megapixels;
      // Update ratio buttons
      DOM.ratioGrid.querySelectorAll('.r-btn, .p-btn').forEach(b=>{
        b.classList.toggle('active',b.dataset.ratio===S.aspectRatio);
      });
      // Update count buttons
      DOM.countGroup.querySelectorAll('.c-btn, .p-btn').forEach(b=>{
        b.classList.toggle('active',+b.dataset.count===S.numOutputs);
      });
      updBtn();
      switchTab(1);
      toast('已加载，可修改后重新生成','info');
    });
  }
  // Close modal on bg click
  document.getElementById('histModal')?.addEventListener('click',function(e){
    if(e.target===this) closeHistModal();
  });

  // ═══ Template Selector ═══
  const templateSelect = document.getElementById('templateSelect');
  let templateData = { categories: [], templates: [] };

  async function loadTemplates() {
    try {
      const [catRes, tplRes] = await Promise.all([
        api('GET', '/api/templates/categories'),
        api('GET', '/api/templates'),
      ]);
      templateData.categories = catRes.categories || [];
      templateData.templates = tplRes.templates || [];

      // Populate dropdown with optgroups
      templateSelect.innerHTML = '<option value="">无模板</option>';
      templateData.categories.forEach(cat => {
        const grp = document.createElement('optgroup');
        grp.label = (cat.title && cat.title.zh) || cat.value || cat.id;
        const tpls = templateData.templates.filter(t => t.category === cat.value);
        tpls.forEach(tpl => {
          const opt = document.createElement('option');
          opt.value = tpl.id;
          opt.textContent = (tpl.title && tpl.title.zh) || tpl.id;
          grp.appendChild(opt);
        });
        if (tpls.length) templateSelect.appendChild(grp);
      });
    } catch(e) { console.warn('模板加载失败', e); }
  }

  templateSelect.addEventListener('change', () => {
    const tplId = templateSelect.value;
    if (!tplId) return;
    const tpl = templateData.templates.find(t => t.id === tplId);
    if (!tpl) return;
    // Build structured prompt from template
    const cat = templateData.categories.find(c => c.value === tpl.category);
    const catName = cat ? (cat.title && cat.title.zh) || cat.value : '';
    let prompt = '【' + catName + '】' + (tpl.title && tpl.title.zh ? ' - ' + tpl.title.zh : '') + '\n\n';
    prompt += (tpl.description && tpl.description.zh) || tpl.description || '';
    if (tpl.guidance && tpl.guidance.zh) {
      prompt += '\n\n💡 提示：' + tpl.guidance.zh.join('；');
    }
    if (tpl.pitfalls && tpl.pitfalls.zh) {
      prompt += '\n⚠️ 避免：' + tpl.pitfalls.zh.join('；');
    }
    DOM.promptInput.value = prompt;
    S.prompt = prompt;
    DOM.charCount.textContent = prompt.length + ' / 4000';
    updBtn();
    toast('已应用模板：「' + ((tpl.title && tpl.title.zh) || tpl.id) + '」', 'info');
  });

  // ═══ AI Assist ═══
  const aiModal = document.getElementById('aiModal');
  const aiCats = document.getElementById('aiCats');
  const aiTpls = document.getElementById('aiTpls');
  const aiResult = document.getElementById('aiResult');
  const aiTips = document.getElementById('aiTips');
  const aiStep1 = document.getElementById('aiStep1');
  const aiStep2 = document.getElementById('aiStep2');
  const aiStep3 = document.getElementById('aiStep3');
  const btnAiBack = document.getElementById('btnAiBack');
  const btnAiUse = document.getElementById('btnAiUse');
  const btnCloseAi = document.getElementById('btnCloseAi');
  let aiState = { category: null, template: null };

  const aiAssistBtn = document.getElementById('btnAiAssist');
  if (aiAssistBtn) {
    aiAssistBtn.addEventListener('click', () => {
      aiState = { category: null, template: null };
      aiStep1.style.display = ''; aiStep2.style.display = 'none'; aiStep3.style.display = 'none';
      btnAiBack.style.display = 'none';
      aiModal.style.display = 'flex';
      renderAiCats();
    });
  }

  function renderAiCats() {
    aiCats.innerHTML = '';
    templateData.categories.forEach(cat => {
      const name = (cat.title && cat.title.zh) || cat.value || cat.id;
      const tplCount = templateData.templates.filter(t => t.category === cat.value).length;
      if (!tplCount) return;
      const btn = document.createElement('button');
      btn.className = 'ai-cat-btn';
      btn.innerHTML = name + '<span style="color:var(--text3);font-size:.65rem"> · ' + tplCount + '</span>';
      btn.addEventListener('click', () => {
        aiState.category = cat;
        renderAiTpls(cat.value);
        aiStep1.style.display = 'none'; aiStep2.style.display = '';
        btnAiBack.style.display = 'inline-flex';
      });
      aiCats.appendChild(btn);
    });
  }

  function renderAiTpls(catValue) {
    aiTpls.innerHTML = '';
    const tpls = templateData.templates.filter(t => t.category === catValue);
    tpls.forEach(tpl => {
      const btn = document.createElement('button');
      btn.className = 'ai-tpl-btn';
      btn.innerHTML = '<div>' + ((tpl.title && tpl.title.zh) || tpl.id) + '</div>';
      if (tpl.description && tpl.description.zh) {
        btn.innerHTML += '<div class="tpl-desc">' + tpl.description.zh.slice(0, 50) + '…</div>';
      }
      btn.addEventListener('click', () => {
        aiState.template = tpl;
        buildAiPrompt(tpl);
      });
      aiTpls.appendChild(btn);
    });
  }

  function buildAiPrompt(tpl) {
    const cat = aiState.category;
    const catName = cat ? (cat.title && cat.title.zh) || cat.value : '';
    let prompt = '【' + catName + '】' + (tpl.title && tpl.title.zh ? ' - ' + tpl.title.zh : '') + '\n\n';
    prompt += (tpl.description && tpl.description.zh) || tpl.description || '';
    if (tpl.guidance && tpl.guidance.zh) {
      prompt += '\n\n💡 提示：' + tpl.guidance.zh.join('；');
    }
    if (tpl.pitfalls && tpl.pitfalls.zh) {
      prompt += '\n⚠️ 避免：' + tpl.pitfalls.zh.join('；');
    }
    aiResult.value = prompt;
    aiTips.textContent = '💡 ' + ((tpl.useWhen && tpl.useWhen.zh) || '选择合适的参数，点击下方按钮使用此提示词');
    aiStep2.style.display = 'none'; aiStep3.style.display = '';
    btnAiBack.style.display = 'inline-flex';
  }

  btnAiBack.addEventListener('click', () => {
    if (aiStep3.style.display !== 'none' && aiStep3.style.display !== '') {
      aiStep3.style.display = 'none'; aiStep2.style.display = '';
    } else if (aiStep2.style.display !== 'none' && aiStep2.style.display !== '') {
      aiStep2.style.display = 'none'; aiStep1.style.display = '';
      btnAiBack.style.display = 'none';
    }
  });

  btnAiUse.addEventListener('click', () => {
    if (aiResult.value.trim()) {
      DOM.promptInput.value = aiResult.value;
      S.prompt = aiResult.value;
      DOM.charCount.textContent = S.prompt.length + ' / 4000';
      updBtn();
      aiModal.style.display = 'none';
      switchTab(1);
      toast('提示词已填入，可修改后生成', 'success');
    }
  });

  if (btnCloseAi) btnCloseAi.addEventListener('click', () => { aiModal.style.display = 'none'; });
  aiModal.addEventListener('click', function(e) { if (e.target === this) this.style.display = 'none'; });

  // ═══ Case Browser ═══
  const caseGrid = document.getElementById('caseGrid');
  const caseFilter = document.getElementById('caseFilter');
  const caseCount = document.getElementById('caseCount');
  const caseEmpty = document.getElementById('caseEmpty');
  const casePages = document.getElementById('casePages');
  let S2 = { page: 1, limit: 18, total: 0, category: '', language: '', cases: [], categories: [], languages: [] };

  async function loadCases() {
    caseGrid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--text3)">加载案例中…</div>';
    try {
      const catParam = S2.category ? '&category=' + encodeURIComponent(S2.category) : '';
      const langParam = S2.language ? '&language=' + S2.language : '';
      const listPromise = api('GET', '/api/cases?page=' + S2.page + '&limit=' + S2.limit + catParam + langParam);
      // Always fetch categories/languages (don't cache to avoid stale data)
      const catPromise = api('GET', '/api/cases/categories');
      const [listRes, catRes] = await Promise.all([listPromise, catPromise]);
      S2.total = listRes.total || 0;
      S2.cases = listRes.cases || [];
      S2.categories = catRes.categories || [];
      S2.languages = catRes.languages || [];
      renderCaseFilter();
      renderCases();
    } catch(e) { caseGrid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--text3)">加载失败</div>'; }
  }

  function renderCaseFilter() {
    caseFilter.innerHTML = '<button class="cf-btn' + (!S2.category && !S2.language ? ' active' : '') + '" data-cat="">全部</button>';
    // Category buttons
    S2.categories.forEach(c => {
      const btn = document.createElement('button');
      btn.className = 'cf-btn' + (c.name === S2.category ? ' active' : '');
      btn.dataset.cat = c.name;
      btn.textContent = c.name + ' (' + c.count + ')';
      btn.addEventListener('click', () => {
        S2.category = c.name;
        S2.language = '';
        S2.page = 1;
        loadCases();
      });
      caseFilter.appendChild(btn);
    });
    // Language separator
    const sep = document.createElement('span');
    sep.className = 'cf-sep';
    sep.textContent = '|';
    caseFilter.appendChild(sep);
    // Language filter buttons
    S2.languages.forEach(l => {
      const btn = document.createElement('button');
      btn.className = 'cf-btn lang' + (l.value === S2.language ? ' active' : '');
      btn.dataset.lang = l.value;
      btn.textContent = l.name + ' (' + l.count + ')';
      btn.addEventListener('click', () => {
        S2.language = l.value;
        S2.category = '';
        S2.page = 1;
        loadCases();
      });
      caseFilter.appendChild(btn);
    });
    // Reset handler for "全部"
    caseFilter.firstChild.addEventListener('click', () => {
      S2.category = '';
      S2.language = '';
      S2.page = 1;
      loadCases();
    });
  }

  function renderCases() {
    caseCount.textContent = '共 ' + S2.total + ' 个案例';
    if (!S2.cases.length) { caseGrid.innerHTML = ''; caseEmpty.style.display = ''; casePages.style.display = 'none'; return; }
    caseEmpty.style.display = 'none';
    caseGrid.innerHTML = '';
    S2.cases.forEach((c, i) => {
      const src = c.image_url || '';
      const card = document.createElement('div');
      card.className = 'case-card';
      card.style.animationDelay = (i * 0.04) + 's';
      card.innerHTML = (src ? '<img src="' + esc(src) + '" alt="" loading="lazy">' : '<div class="skel"></div>') +
        '<div class="case-card-info">' +
        '<div class="case-card-cat">' + esc(c.category || '') + '</div>' +
        '<div class="case-card-title">' + esc(c.title || c.prompt_short || '') + '</div></div>';
      card.addEventListener('click', () => {
        openCaseDetail(c);
      });
      caseGrid.appendChild(card);
    });
    // Pagination
    const pages = Math.ceil(S2.total / S2.limit);
    if (pages > 1) {
      casePages.style.display = 'flex'; let h = '';
      if (S2.page > 1) h += '<button class="btn btn-s btn-sm" onclick="window._casePage(' + (S2.page - 1) + ')">←</button>';
      h += '<span>' + S2.page + '/' + pages + '</span>';
      if (S2.page < pages) h += '<button class="btn btn-s btn-sm" onclick="window._casePage(' + (S2.page + 1) + ')">→</button>';
      casePages.innerHTML = h;
    } else casePages.style.display = 'none';
  }
  window._casePage = function(p) {
    if (p < 1) return;
    S2.page = p; loadCases();
  };

  // ═══ Case Detail Modal ═══
  const caseModal = document.getElementById('caseModal');
  const caseDetailImg = document.getElementById('caseDetailImg');
  const caseDetailInfo = document.getElementById('caseDetailInfo');
  let _currentCase = null;

  function openCaseDetail(c) {
    _currentCase = c;
    // Image
    const src = c.image_url || '';
    caseDetailImg.innerHTML = src ? '<img src="' + esc(src) + '" alt="" onclick="window._lb(\'' + esc(src) + '\')">' : '<div style="height:200px;background:var(--bg2);border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;color:var(--text3);font-size:.8rem">无图片</div>';
    // Info
    const cat = c.category || '-';
    const title = c.title || '-';
    const styles = (c.styles || []).join(', ') || '-';
    const prompt = c.prompt || c.title || '';
    const sourceLabel = c.sourceLabel || '';
    const sourceUrl = c.sourceUrl || '';
    caseDetailInfo.innerHTML =
      '<div class="row"><span class="lbl">分类</span><span class="val">' + esc(cat) + '</span></div>' +
      '<div class="row"><span class="lbl">标题</span><span class="val">' + esc(title) + '</span></div>' +
      '<div class="row"><span class="lbl">风格</span><span class="val">' + esc(styles) + '</span></div>' +
      (sourceUrl ? '<div class="row"><span class="lbl">来源</span><span class="val"><a href="' + esc(sourceUrl) + '" target="_blank" style="color:var(--accent)">' + esc(sourceLabel || '查看原文') + '</a></span></div>' : '') +
      '<div class="row" style="margin-top:4px"><span class="lbl">提示词</span><span class="val prompt">' + esc(prompt) + '</span></div>';
    caseModal.style.display = 'flex';
  }

  function closeCaseModal() { caseModal.style.display = 'none'; _currentCase = null; }

  document.getElementById('btnCloseCase').addEventListener('click', closeCaseModal);
  document.getElementById('btnCloseCase2').addEventListener('click', closeCaseModal);
  document.getElementById('btnCaseUse').addEventListener('click', () => {
    if (!_currentCase) return;
    const prompt = _currentCase.prompt || _currentCase.title || '';
    if (prompt) {
      DOM.promptInput.value = prompt;
      S.prompt = prompt;
      DOM.charCount.textContent = prompt.length + ' / 4000';
      updBtn();
      closeCaseModal();
      switchTab(1);
      toast('已加载案例提示词，可修改后生成', 'success');
    }
  });
  caseModal.addEventListener('click', function(e) { if (e.target === this) closeCaseModal(); });

  // ═══ Metadata ═══
  let metaTmpPath = '';
  let metaFiles = [];

  // Drag & drop
  const metaDrop = document.getElementById('metaDrop');
  const metaFileInput = document.getElementById('metaFileInput');

  metaDrop.addEventListener('click', () => metaFileInput.click());
  metaFileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleMetaFiles(e.target.files);
  });

  metaDrop.addEventListener('dragover', (e) => { e.preventDefault(); metaDrop.classList.add('dragover'); });
  metaDrop.addEventListener('dragleave', () => { metaDrop.classList.remove('dragover'); });
  metaDrop.addEventListener('drop', (e) => {
    e.preventDefault();
    metaDrop.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleMetaFiles(e.dataTransfer.files);
  });

  function handleMetaFiles(files) {
    metaFiles = Array.from(files);
    renderThumbs();
  }

  function renderThumbs() {
    const container = document.getElementById('metaThumbs');
    if (!metaFiles.length) {
      container.innerHTML = '<div class="meta-thumbs-empty">拖拽图片到上方上传栏</div>';
      document.getElementById('metaFileInfo').textContent = '未选择文件';
      return;
    }
    let html = '';
    metaFiles.forEach((f, i) => {
      const url = URL.createObjectURL(f);
      html += '<div class="meta-thumb selected" data-idx="' + i + '">' +
        '<img src="' + url + '" alt="">' +
        '<span class="mt-check">✓</span>' +
        '<div class="mt-name">' + esc(f.name) + '</div></div>';
    });
    container.innerHTML = html;
    document.getElementById('metaFileInfo').textContent = metaFiles.length + ' 张图片';
    // 读取第一张的 EXIF 填入表单
    readFirstMeta();
  }

  async function readFirstMeta() {
    if (!metaFiles.length) return;
    const formData = new FormData();
    formData.append('file', metaFiles[0]);
    try {
      const r = await fetch('/api/metadata/read', { method: 'POST', body: formData });
      const resp = await r.json();
      if (resp.exif) {
        metaTmpPath = resp.tmp_path || '';
        document.getElementById('metaArtist').value = resp.exif.Artist || '';
        document.getElementById('metaCopyright').value = resp.exif.Copyright || '';
        document.getElementById('metaDescription').value = resp.exif.ImageDescription || '';
        document.getElementById('metaSoftware').value = resp.exif.Software || '';
        document.getElementById('metaExifContent').textContent = JSON.stringify(resp.exif, null, 2);
      }
    } catch(e) {}
  }

  // 恢复上次保存的表单值
  restoreMetaForm();

  // PS Presets
  const metaPreset = document.getElementById('metaPreset');
  api('GET', '/api/metadata/presets').then(r => {
    (r.presets || []).forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label + ' — ' + p.desc;
      metaPreset.appendChild(opt);
    });
  });
  metaPreset.addEventListener('change', () => {
    const p = metaPreset.value;
    if (!p) return;
    api('GET', '/api/metadata/presets').then(r => {
      const preset = (r.presets || []).find(x => x.id === p);
      if (preset && preset.data) {
        document.getElementById('metaArtist').value = preset.data.artist || '';
        document.getElementById('metaCopyright').value = preset.data.copyright || '';
        document.getElementById('metaDescription').value = preset.data.description || '';
        document.getElementById('metaSoftware').value = preset.data.software || '';
        toast('已应用预设: ' + preset.label, 'info');
      }
    });
  });

  // Read button (re-fetch EXIF display from current data)
  const btnMetaRead = document.getElementById('btnMetaRead');
  if (btnMetaRead) btnMetaRead.addEventListener('click', () => {
    if (!metaTmpPath) { toast('请先拖入图片', 'error'); return; }
    // Re-display already loaded EXIF
    const exifEl = document.getElementById('metaExifContent');
    if (exifEl.textContent && exifEl.textContent !== '{}') {
      toast('✅ 已显示当前 EXIF', 'success');
    }
  });

  // 保存/恢复表单到 localStorage
  function saveMetaForm() {
    const data = {
      artist: document.getElementById('metaArtist').value,
      copyright: document.getElementById('metaCopyright').value,
      description: document.getElementById('metaDescription').value,
      software: document.getElementById('metaSoftware').value,
    };
    localStorage.setItem('img2-meta-form', JSON.stringify(data));
  }
  function restoreMetaForm() {
    try {
      const saved = localStorage.getItem('img2-meta-form');
      if (saved) {
        const data = JSON.parse(saved);
        if (data.artist) document.getElementById('metaArtist').value = data.artist;
        if (data.copyright) document.getElementById('metaCopyright').value = data.copyright;
        if (data.description) document.getElementById('metaDescription').value = data.description;
        if (data.software) document.getElementById('metaSoftware').value = data.software;
      }
    } catch(e) {}
  }

  // Write button — upload first file then save
  document.getElementById('btnMetaWrite').addEventListener('click', async () => {
    if (!metaFiles.length) { toast('请先拖入图片', 'error'); return; }
    // Upload first file if no tmp path
    let tmpPath = metaTmpPath;
    if (!tmpPath) {
      const fd = new FormData(); fd.append('file', metaFiles[0]);
      const r = await fetch('/api/metadata/read', { method: 'POST', body: fd });
      const d = await r.json();
      tmpPath = d.tmp_path || '';
    }
    if (!tmpPath) { toast('上传失败', 'error'); return; }
    const formData = new FormData();
    formData.append('tmp_path', tmpPath);
    formData.append('artist', document.getElementById('metaArtist').value);
    formData.append('copyright', document.getElementById('metaCopyright').value);
    formData.append('description', document.getElementById('metaDescription').value);
    formData.append('software', document.getElementById('metaSoftware').value);
    try {
      const r = await fetch('/api/metadata/write', { method: 'POST', body: formData });
      const resp = await r.json();
      if (resp.download_url) {
        saveMetaForm();
        toast('✅ 元数据已保存', 'success');
        const a = document.createElement('a');
        a.href = resp.download_url;
        a.download = '';
        a.click();
      }
    } catch(e) { toast('保存失败: ' + e.message, 'error'); }
  });
  // 表单输入时自动保存
  ['metaArtist','metaCopyright','metaDescription','metaSoftware'].forEach(id => {
    document.getElementById(id).addEventListener('input', saveMetaForm);
  });

  // Batch button
  document.getElementById('btnMetaBatch').addEventListener('click', async () => {
    if (!metaFiles.length) { toast('请先选择多张图片', 'error'); return; }
    const formData = new FormData();
    metaFiles.forEach(f => formData.append('files', f));
    formData.append('artist', document.getElementById('metaArtist').value);
    formData.append('copyright', document.getElementById('metaCopyright').value);
    formData.append('description', document.getElementById('metaDescription').value);
    formData.append('software', document.getElementById('metaSoftware').value);

    document.getElementById('metaBatch').style.display = '';
    document.getElementById('metaBatchStatus').textContent = '处理中...';
    document.getElementById('metaBatchLog').innerHTML = '';
    const logBatch = (msg) => {
      const d = document.createElement('div'); d.className = 'l'; d.textContent = msg;
      document.getElementById('metaBatchLog').appendChild(d);
    };

    try {
      logBatch('📦 开始批量处理 ' + metaFiles.length + ' 张图片...');
      const r = await fetch('/api/metadata/batch', { method: 'POST', body: formData });
      const resp = await r.json();
      if (resp.download_url) {
        document.getElementById('metaBatchStatus').textContent = '✅ 完成';
        document.getElementById('metaBatchBar').className = 'g-fill';
        document.getElementById('metaBatchBar').style.width = '100%';
        logBatch('✅ 处理完成! 共 ' + (resp.results||[]).length + ' 张');
        // Download zip
        const a = document.createElement('a');
        a.href = resp.download_url;
        a.download = '';
        a.click();
        toast('批量处理完成', 'success');
      }
    } catch(e) { logBatch('❌ ' + e.message); toast('批量处理失败', 'error'); }
  });

  // ── Init ──
  (async function init() {
    renderRatios();
    try {
      const [s1,s2,s3]=await Promise.all([api('GET','/api/config/status'),api('GET','/api/config/settings'),api('GET','/api/config/models')]);
      S.apiConfigured=s1.api_configured||false;
      if(s2){S.userApiKey=s2.api_key||'';S.userBaseUrl=s2.base_url||'';}
      S.models=(s3&&s3.models)?s3.models:[];
    } catch(e){console.error('Init:',e);}
    renderModels(); updStatus(); renderSettings(); updBtn(); loadHistory();

    // Load templates
    await loadTemplates();

    // Load cases when navigating to tab 3
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
      if (item.dataset.tab === '3') {
        item.addEventListener('click', () => {
          loadCases();
        });
      }
    });

    DOM.genBox.style.display='none';

    // Auto-query balance on load if configured
    if (S.apiConfigured) {
      queryBalance();
    }
  })();
})();
