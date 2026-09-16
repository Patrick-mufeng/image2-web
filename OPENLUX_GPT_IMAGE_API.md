# OpenLux GPT-Image 系列接口文档

> 来源：[doc.openlux.ai](https://doc.openlux.ai) 官方接口参考页，抓取整理于 2026-09-13。
> 覆盖本工具使用的全部 GPT-Image 系列端点：文生图（generations）× 3 个模型页、图生图（edits）× 2 个模型页，以及通用说明。
>
> - **Base URL**：`https://api.openlux.ai`
> - **认证**：请求头 `Authorization: Bearer <API Key>`
> - **计费方式**：按次计费（quota_type=1）。2026-09-13 实测 `/api/pricing`：`gpt-image-2-c` $0.12/张，`gpt-image-2.5-flare-c` / `gpt-image-2.5-sunburst-c` $0.16/张。分组费率（group_ratio）：`Gpt-Image-1` ×0.07353、`Gpt-Image-2` ×0.09192、`Gpt-Image-3` ×0.13787。**分组是令牌级属性**（建令牌时选定，网关按令牌分组路由渠道），请求本身不传分组。
> - **模型名注意**：文档枚举名**不带** `-c` 后缀（如 `gpt-image-2.5-flare`），但令牌实际可用模型（`GET /v1/models` 实测）为带 `-c` 的调试台变体：`gpt-image-2.5-flare-c`、`gpt-image-2.5-sunburst-c`、`gpt-image-2-c`。以 `/v1/models` 返回为准。
> - **响应结构注意**：部分页面的 200 schema 写的是 `{created, data}` 数组结构，但请求示例/响应示例又展示 `chat.completion` 结构（`{id, object, created, choices, usage}`），两种在文档中并存。不同渠道可能返回不同结构，客户端解析需做兼容（见各页「响应」小节的标注）。

## 目录

- [1. 通用约定](#1-通用约定)
- [2. 文生图 POST /v1/images/generations — gpt-image-2.5](#2-文生图-post-v1imagesgenerations--gpt-image-25)
- [3. 文生图 POST /v1/images/generations — gpt-image-2](#3-文生图-post-v1imagesgenerations--gpt-image-2)
- [4. 文生图 POST /v1/images/generations — gpt-image-2-c（含多图参考）](#4-文生图-post-v1imagesgenerations--gpt-image-2c含多图参考)
- [5. 图生图 POST /v1/images/edits — gpt-image-2.5](#5-图生图-post-v1imagesedits--gpt-image-25)
- [6. 图生图 POST /v1/images/edits — 通用说明（gpt-image-2 及其他）](#6-图生图-post-v1imagesedits--通用说明gpt-image-2-及其他)
- [7. 错误响应](#7-错误响应)
- [8. 分组（Group）专题](#8-分组group专题)
- [附录 A：本项目对接核对记录](#附录-a本项目对接核对记录)

---

## 1. 通用约定

| 项 | 说明 |
|----|------|
| Base URL | `https://api.openlux.ai`（旧配置若带 `/v1` 后缀需去掉，避免拼出 `/v1/v1/...`） |
| 认证 | `Authorization: Bearer <API Key>` |
| 文生图 Content-Type | `application/json` |
| 图生图 Content-Type | `multipart/form-data` |
| 429 | 上游「系统繁忙」，官方建议退避重试（本项目实测 5s/10s/20s 退避有效） |
| 400 | 参数校验失败或不合法，返回 `NewApiError`（见[第 7 节](#7-错误响应)） |

---

## 2. 文生图 POST /v1/images/generations — gpt-image-2.5

> 文档页：[创建 gpt-image-2.5](https://doc.openlux.ai/reference/v1?op=post-v1-images-generations&leaf=513295251)
>
> 给定一个提示，该模型将返回一个或多个预测的完成。官方文档：https://platform.openai.com/docs/api-reference/images/create

### 请求参数（application/json）

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `model` | string | ✅ | 模型名。枚举：`gpt-image-2.5-flare`（更快，适合日常/高并发生成）、`gpt-image-2.5-sunburst`（更高精度，适合精修和创意成片） |
| `prompt` | string | ✅ | 所需图像的文本描述。**最大长度为 1000 个字符** |
| `size` | string |  | 图片尺寸，见下方尺寸枚举与严格限制规则 |
| `format` | string |  | 图片格式，可选 `png`、`jpeg`、`webp`。透明背景请使用 `png` 或 `webp`。**（官方字段名为 `output_format`，本网关与 gpt-image-2 调试台统一用 `format`）** |
| `quality` | string |  | 图片画质，可选 `low`、`medium`、`high`、`xhigh`、`max`、`auto`（默认）。相对 gpt-image-2 **新增 xhigh、max**。low 适合草稿；xhigh / max 更精细但延迟和费用更高 |
| `n` | integer | ✅ | 要生成的图像数。必须介于 1 和 10 之间。**未传时网关默认 1** |
| `response_format` | string |  | 返回格式。枚举：`url`（返回图片 URL）、`b64_json`（返回 Base64 图片数据） |
| `background` | string |  | 背景。枚举：`auto`（默认）、`opaque`、`transparent`。**`transparent` 时 `format` 必须为 `png` 或 `webp`** |
| `moderation` | string |  | 内容审核严格度。枚举：`auto`（默认）、`low` |

### size 枚举

| 值 | 说明 |
|----|------|
| `1024x1024` | 正方形 |
| `1536x1024` | 横版 |
| `1024x1536` | 竖版 |
| `2048x2048` | 2K 正方形 |
| `2048x1152` | 2K 横版 |
| `3840x2160` | 4K 横版 |
| `2160x3840` | 4K 竖版 |
| `auto` | 默认 |

**尺寸严格限制规则（自定义尺寸需同时满足）：**

1. 图片最大边长 ≤ 3840px
2. 宽高两边像素均为 16px 的倍数
3. 长边 / 短边 比值 ≤ 3:1
4. 总像素范围：最小 655,360 ~ 最大 8,294,400（= 3840×2160）
5. **超过 2560x1440 的分辨率属实验性能力**

### 请求示例

```json
{
  "model": "gpt-image-2.5-flare",
  "prompt": "产品静物：哑光黑机械键盘，影棚灯光，无文字",
  "n": 1,
  "size": "1536x1024",
  "quality": "medium",
  "format": "webp",
  "response_format": "url"
}
```

```bash
curl -X POST "https://api.openlux.ai/v1/images/generations" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2.5-flare",
    "prompt": "产品静物：哑光黑机械键盘，影棚灯光，无文字",
    "n": 1,
    "size": "1536x1024",
    "quality": "medium",
    "format": "webp",
    "response_format": "url"
  }'
```

### 响应

**200** — `PostV1ImagesGenerationsResponse`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `created` | integer | Unix 时间戳（秒） |
| `data` | array | 数据载荷（常为 Base64 或结构化对象） |

```json
{
  "created": 1773100000,
  "data": [ { "...": "..." } ]
}
```

**400** — 参数校验失败或请求不合法，见[第 7 节](#7-错误响应)。

---

## 3. 文生图 POST /v1/images/generations — gpt-image-2

> 文档页：[创建 gpt-image-2](https://doc.openlux.ai/reference/v1?op=post-v1-images-generations&leaf=453199915)

### 请求参数（application/json）

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `model` | string | ✅ | 模型名 |
| `prompt` | string | ✅ | 所需图像的文本描述。**最大长度为 1000 个字符** |
| `n` | integer | ✅ | 要生成的图像数。必须介于 1 和 10 之间 |
| `size` | string |  | 图片尺寸。枚举与严格限制规则与 gpt-image-2.5 相同（1024x1024 / 1536x1024 / 1024x1536 / 2048x2048 / 2048x1152 / 3840x2160 / 2160x3840 / auto；最大边 ≤3840、16px 倍数、比例 ≤3:1、总像素 655,360 ~ 8,294,400）。此页未标注「实验性」说明 |
| `format` | string |  | 图片格式，可选 `png`、`jpeg`、`webp` |
| `quality` | string |  | 图片画质，可选 `low`、`medium`、`high`、`auto`（默认）。**没有 xhigh / max** |
| `response_format` | string |  | 枚举：`url`、`b64_json` |

### 请求示例

```json
{
  "model": "gpt-image-2",
  "prompt": "A childrens book drawing of a veterinarian using a stethoscope to listen to the heartbeat of a baby otter.",
  "size": "1024x1024",
  "format": "jpeg",
  "quality": "low",
  "n": 1
}
```

```bash
curl -X POST "https://api.openlux.ai/v1/images/generations" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "A childrens book drawing of a veterinarian using a stethoscope to listen to the heartbeat of a baby otter.",
    "size": "1024x1024",
    "format": "jpeg",
    "quality": "low",
    "n": 1
  }'
```

### 响应

**200** — schema 声明为 `{created, data}`，**但文档响应示例为 chat.completion 结构**：

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "choices": [ { "...": "..." } ],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

> ⚠️ 同一页面中 schema 与示例不一致，说明网关不同渠道可能返回两种结构，解析时需同时兼容。

**400** — 见[第 7 节](#7-错误响应)。

---

## 4. 文生图 POST /v1/images/generations — gpt-image-2-c（含多图参考）

> 文档页：[创建 gpt-image-2-c](https://doc.openlux.ai/reference/v1?op=post-v1-images-generations&leaf=448157414)
>
> gpt-image-2-c 支持在 generations 端点直接传 `image` 数组实现**多图参考/合并编辑**。

### 请求参数（application/json）

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `model` | string | ✅ | **固定为 `gpt-image-2-c`** |
| `size` | string |  | 生成图像的尺寸。对于 GPT 图像模型，**必须是 `1024x1024`、`1536x1024`（横版）、`1024x1536`（竖版）** —— 仅此三档，不支持 2K/4K |
| `n` | integer |  | 要生成的图像数量 |
| `prompt` | string | ✅ | 所需图像的文本描述 |
| `image` | array |  | 要编辑的图片。必须是受支持的图片文件或图片数组。**最大可传 5 张**（传 URL 或文件） |
| `response_format` | string |  | 枚举：`url`、`b64_json |

> ⚠️ 此模型**没有** `quality`、`format`、`background`、`moderation` 参数；`size` 仅三档。额外传参可能被上游 400 拒绝。

### 请求示例（多图参考 / 合并）

```json
{
  "model": "gpt-image-2-c",
  "size": "1024x1024",
  "n": 1,
  "prompt": "将他们合并在一起",
  "image": [
    "https://imageproxy.zhongzhuan.chat/api/proxy/image/c42f4361295d6d70e3228498855c5814.png",
    "https://imageproxy.zhongzhuan.chat/api/proxy/image/5b718c199e90b1fbbe06e7db9d88ebab.jpg"
  ]
}
```

```bash
curl -X POST "https://api.openlux.ai/v1/images/generations" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-2-c",
    "size": "1024x1024",
    "n": 1,
    "prompt": "将他们合并在一起",
    "image": [
      "https://imageproxy.zhongzhuan.chat/api/proxy/image/c42f4361295d6d70e3228498855c5814.png",
      "https://imageproxy.zhongzhuan.chat/api/proxy/image/5b718c199e90b1fbbe06e7db9d88ebab.jpg"
    ]
  }'
```

### 响应

**200** — `{created, data}` 结构：

```json
{
  "created": 1776909189,
  "data": [ { "...": "..." } ]
}
```

**400** — 见[第 7 节](#7-错误响应)。

---

## 5. 图生图 POST /v1/images/edits — gpt-image-2.5

> 文档页：[编辑 gpt-image-2.5](https://doc.openlux.ai/reference/v1?op=post-v1-images-edits&leaf=513297453)
>
> 官方文档：https://platform.openai.com/docs/api-reference/images/createEdit

### 请求参数（multipart/form-data）

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `model` | string | ✅ | 模型名。枚举：`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst` |
| `prompt` | string | ✅ | 编辑指令。**最大长度为 1000 个字符** |
| `image` | string · binary | ✅ | 待编辑/参考图。**可重复传多个 `image` 字段，最多 16 张** |
| `mask` | string · binary |  | 蒙版图，可选。**透明区域为需要填充/修改的区域**。需与 `image` 同尺寸 |
| `size` | string |  | 图片尺寸，规则与 generations 相同。常用：`auto`、`1024x1024`、`1536x1024`、`1024x1536`、`2048x2048`、`2048x1152`、`3840x2160`、`2160x3840` |
| `format` | string |  | 图片格式，可选 `png`、`jpeg`、`webp` |
| `quality` | string |  | 图片画质，可选 `low`、`medium`、`high`、`xhigh`、`max`、`auto`（默认） |
| `n` | integer | ✅ | 要生成的图像数。必须介于 1 和 10 之间 |
| `background` | string |  | 背景。可选 `auto`、`opaque`、`transparent` |
| `moderation` | string |  | 内容审核严格度。可选 `auto`（默认）、`low` |
| `response_format` | string |  | `url`：返回图片 URL；`b64_json`：返回 Base64 图片数据 |

### 请求示例

```bash
curl -X POST "https://api.openlux.ai/v1/images/edits" \
  -F "model=gpt-image-2.5-flare" \
  -F "prompt=一直可爱的小猪" \
  -F "image=@/path/to/file" \
  -F "mask=@/path/to/mask" \
  -F "size=1024x1024" \
  -F "format=" \
  -F "quality=" \
  -F "n=1" \
  -F "background=" \
  -F "moderation=" \
  -F "response_format="
```

### 响应

**200** — schema 声明为 `PostV1ImagesEditsResponse`（chat.completion 风格）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `choices` | array | 候选结果列表 |
| `created` | integer | 创建时间（Unix 时间戳） |
| `id` | string | 资源或任务 ID |
| `object` | string | 对象类型标识，如 `chat.completion` |
| `usage` | object | Token 用量统计 |

而页面底部的响应示例又展示 `{created, data}` 结构：

```json
{
  "created": 1773100000,
  "data": [ { "...": "..." } ]
}
```

> ⚠️ 同一页面 schema 与示例不一致。实际渠道返回需实测；客户端应对 `data` 与 `choices` 两种结构都做兼容。

**400** — 见[第 7 节](#7-错误响应)。

---

## 6. 图生图 POST /v1/images/edits — 通用说明（gpt-image-2 及其他）

> 文档页：[编辑 gpt-image-2](https://doc.openlux.ai/reference/v1?op=post-v1-images-edits&leaf=446294920)（文档中存在两个相同内容的「编辑 gpt-image-2」页面；此页内容为 OpenAI 通用描述，以 gpt-image-1 / dall-e-2 口径书写）
>
> 官方文档：https://platform.openai.com/docs/api-reference/images/createEdit

### 请求参数（multipart/form-data）

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `image` | string | ✅ | 要编辑的图片。必须是受支持的图片文件或图片数组。对于 gpt-image-1，每张图片应为小于 25MB 的 png、webp 或 jpg 文件。对于 dall-e-2，只能提供一张图片，且应为小于 4MB 的方形 png 文件 |
| `prompt` | string | ✅ | 所需图像的文本描述。dall-e-2 的最大长度为 1000 个字符，gpt-image-1 的最大长度为 32000 个字符 |
| `mask` | string | ✅ | 一张附加图片，其完全透明区域（alpha 值为零）指示应编辑 image 位置。如果提供了多张图片，则遮罩将应用于第一张图片。必须是有效的 PNG 文件，小于 4MB，且尺寸与 image 相同 |
| `model` | string | ✅ | 用于生成图像的模型。仅支持 dall-e-2 和 gpt-image-1。除非使用特定于 gpt-image-1 参数，否则默认为 dall-e-2 |
| `n` | integer | ✅ | 要生成的图像数量。必须介于 1 到 10 之间 |
| `quality` | string | ✅ | 生成图像的质量。只有 gpt-image-1 支持 high、medium 和 low 质量。dall-e-2 仅支持 standard 质量。默认为 auto |
| `response_format` | string | ✅ | 返回生成图像的格式。必须是 url 或 b64_json 之一。URL 在图像生成后 60 分钟内有效。此参数仅适用于 dall-e-2，因为 gpt-image-1 始终返回 base64 编码的图像 |
| `size` | string | ✅ | 生成图像的尺寸。对于 gpt-image-1，必须为 1024x1024、1536x1024（横向）、1024x1534（纵向）或 auto（默认值）之一；对于 dall-e-2，必须为 256x256、512x512 或 1024x1024 之一 |

### 请求示例

```bash
curl -X POST "https://api.openlux.ai/v1/images/edits" \
  -F "image=@/path/to/file" \
  -F "prompt=一直可爱的小猪" \
  -F "mask=@/path/to/mask" \
  -F "model=gpt-image-1" \
  -F "n=1" \
  -F "quality=" \
  -F "response_format=" \
  -F "size=1024x1024"
```

### 响应

**200** — chat.completion 结构：

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "choices": [ { "...": "..." } ],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

**400** — 见[第 7 节](#7-错误响应)。

---

## 7. 错误响应

**400** — 参数校验失败或请求不合法，`NewApiError` 结构：

```json
{
  "error": { "...": "..." }
}
```

**429** — 上游「系统繁忙」。官方教程建议稍后重试；本项目实测自动退避（5s / 10s / 20s）重试有效。

其他状态码参见官方教程《HTTP 状态码及其含义》：https://doc.openlux.ai/tutorials/http-status-codes

---

## 8. 分组（Group）专题

> 分组相关内容分散在三处：教程《分组的特殊性及价格差异》（有正文）、《如何新建指定分组的令牌》（**文档站该页正文为空，仅标题**）、以及系统管理接口「新增令牌」中的分组字段。

### 8.1 分组机制（摘自官方教程《分组的特殊性及价格差异》）

> 来源：https://doc.openlux.ai/tutorials/relay-intro-5459008

- **渠道来源差异**：GPT 和 Claude 等模型在不同分组中对应的渠道来源不同，这导致了各分组间价格的差异。
- **价格多样性**：这是市面上 API 价格不统一的根本原因；OpenLux 采取明码实价策略，确保透明度。
- **用户选择**：用户可根据自身需求选择最适合的分组，提供灵活性和个性化选项。
- **分组倍率说明**：
  - 当分组倍率 = 1 时：官方价格的 1 刀，平台也扣 1 刀
  - 当分组倍率 = 1.65 时：官方价格的 1 刀，平台扣 1.65 刀
  - 具体公开分组倍率以本站文档及后台配置为准

**要点：分组是令牌级属性**（创建令牌时选定，网关按令牌分组路由渠道），**生图请求本身不传分组**；实际计费 ≈ 模型按次单价 × 分组倍率。

### 8.2 查询分组费率

文档未单独列出分组费率查询端点；实测分组费率表随公开接口 `GET /api/pricing` 的 `group_ratio` 字段返回（2026-09-13 实测共 **81 个分组**），GPT-Image 相关：

| 分组 | 倍率 group_ratio |
|------|-----------------|
| `Gpt-Image-1` | ×0.07353 |
| `Gpt-Image-2` | ×0.09192 |
| `Gpt-Image-3` | ×0.13787 |

同一接口每个模型的 `enable_groups` 字段标注了该模型在哪些分组下可用（如 `gpt-image-2.5-flare-c` → `["Gpt-Image-1", "Gpt-Image-2", "Gpt-Image-3"]`）。

### 8.3 新建指定分组的令牌

> 教程页 https://doc.openlux.ai/tutorials/relay-intro-5459010 正文为空；以下以系统管理接口文档为准（来源：[新增令牌](https://doc.openlux.ai/reference/system?op=post-api-token&leaf=278500390)）。

**POST `/api/token/`** — 创建新的 API 令牌。成功时 `data` 为完整密钥字符串（形如 `sk-...`），请立即保存。

请求体参数（application/json）：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `name` | string | ✅ | 令牌名字 |
| `remain_quota` | integer | ✅ | 额度（**50w 为 1 刀**） |
| `expired_time` | integer | ✅ | 到期时间戳，单位秒；没有到期限制设置为 `-1` |
| `unlimited_quota` | boolean | ✅ | 无限额度设置 |
| `model_limits_enabled` | boolean | ✅ | 可用模型限制设置 |
| `model_limits` | string | ✅ | 可用模型列表：模型名字按 `,` 号分割 |
| `allow_ips` | string | ✅ | 白名单 IP 列表：按 `\n` 号分割 |
| `group` | string | ✅ | **支持分组，按 `,` 号分割** |
| `selected_groups` | array |  | 请求体示例中出现（数组形式），与 `group` 的关系以实测为准 |
| `mj_image_mode` | string |  | 请求体示例中出现，示例值 `default` |
| `mj_custom_proxy` | string |  | 请求体示例中出现 |

请求示例：

```json
{
  "remain_quota": 250000000000,
  "expired_time": -1,
  "unlimited_quota": false,
  "model_limits_enabled": false,
  "model_limits": "",
  "group": "",
  "mj_image_mode": "default",
  "mj_custom_proxy": "",
  "selected_groups": [],
  "name": "令牌名字",
  "allow_ips": ""
}
```

响应 200 — `ApiSuccessString`：`{"data": "sk-...", "message": "...", "success": true}`。

### 8.4 相关系统接口（与分组/令牌管理配套）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/token/` | GET | 获取令牌列表 |
| `/api/token/search` | GET | 搜索令牌 |
| `/api/token/` | PUT / DELETE | 修改 / 删除令牌（批量修改：`PUT /api/token/batch`） |
| `/api/user/self` | GET | 获取账号信息 |
| `/v1/models` | GET | 获取令牌支持模型 |
| `/api/usage/token/` | GET | 获取令牌使用情况 |

> 注：本项目余额查询用的是 NewAPI 风格的 `/v1/dashboard/billing/subscription` + `/v1/dashboard/billing/usage`（实测可用）；文档正式列出的是 `/api/user/self`，两者可互为备选。

---

## 附录 A：本项目对接核对记录

> 2026-09-13 对照本文档核对 `backend/` 的对接实现，实测接口：`GET /v1/models`、`GET /api/pricing`（令牌：3 个 `-c` 变体模型）。

**已验证正确的对接：**

- 模型目录动态拉取（`/v1/models` + `/api/pricing`，10 分钟缓存 + 内置兜底表）优于写死文档枚举（文档枚举名不带 `-c`，令牌实际是 `-c` 变体）
- 网关字段名用 `format`（非官方 `output_format`）✅
- 2.5 的画质档位含 `xhigh`/`max`；`n` 仅在 >1 时发送 ✅
- 4MP 1:1 取 2880x2880，满足 16px 倍数与总像素 ≤8,294,400 的规则 ✅

**已发现的差距（按严重程度）：**

1. **gpt-image-2-c 尺寸仅三档**（1024x1024 / 1536x1024 / 1024x1536），`SIZE_MAP` 的 15 种组合对该模型未做过滤，选 2MP/4MP 会 400（前端分辨率选项也未按模型过滤）。
2. **prompt 上限错位**：文档为 1000 字符（generations 与 edits 均是），本项目前后端均为 4000。
3. **响应结构兼容**：文档存在 `{data}` 与 chat.completion（`choices`）两种结构并存；本项目只解析 `data`，edits 只认 `b64_json`，建议补 `choices` 兼容并在 0 图时显式报错；edits 建议显式传 `response_format=b64_json`。
4. **多图编辑语义**：文档支持一次传多图（2.5 edits 可重复 `image` 字段最多 16 张；2-c 在 generations 传 `image` 数组最多 5 张）；本项目为逐张串行独立请求，未实现多图融合。
5. **n 上限**：文档 1-10；`edits.py` 仍限制 1-4。
