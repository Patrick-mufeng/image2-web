/**
 * 截图打码：注入到页面里再截图，避免用像素坐标猜位置。
 *
 * 打码对象：
 *   - 账号信息：KEY 名称、余额、本月已用
 *   - 生成图片：历史网格、侧栏最近生成、生成结果区
 *   - 提示词正文：用户自己的菜谱/业务文本（监控面板、侧栏）
 * 不打码：
 *   - 案例展示（公共案例库）
 */
(function () {
  var css = `
  /* ── 账号信息 ── */
  #hdrKeyName, #hdrBalance, #hdrUsage,
  #ftBal, #ftUsage,
  #keyNameText,
  #pageApiKey {
    filter: blur(5px) !important;
    -webkit-filter: blur(5px) !important;
    user-select: none !important;
  }

  /* ── 生成结果图片（自己的产出）── */
  .hist-grid img,
  .side-recent img,
  #imgGrid img,
  .res-card img,
  #lbImg {
    filter: blur(9px) !important;
    -webkit-filter: blur(9px) !important;
  }

  /* ── 用户提示词正文 ── */
  .hist-card-prompt,
  .sr-prompt,
  .sr-info,
  .rp-t,
  .mh-prompt,
  .mon-code-prompt,
  #monReqPrompt,
  #monRes,
  .recent-row .rr-prompt {
    filter: blur(4px) !important;
    -webkit-filter: blur(4px) !important;
  }

  /* ── 请求历史列表里的具体条目（含提示词摘要）── */
  .mh-item .mh-prompt { filter: blur(4px) !important; }
  `;

  var style = document.createElement('style');
  style.id = '__readme_mask__';
  style.textContent = css;
  document.head.appendChild(style);

  return 'mask injected';
})()
