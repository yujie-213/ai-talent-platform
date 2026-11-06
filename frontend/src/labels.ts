export const categoryName: Record<string,string> = {name:'姓名',phone:'电话',email:'邮箱',contact:'联系方式',education:'教育',experience:'经历',project:'项目',skill:'技能',certificate:'证书'}
export const qualityName: Record<string,string> = {manual:'人工维护',pending:'待解析',complete:'资料完整',needs_review:'需核对',identity_conflict:'身份冲突',version_conflict:'档案已更新，需核对',possible_duplicate:'疑似重复',failed:'解析失败'}
export const indexName: Record<string,string> = {pending:'等待更新',ready:'已就绪',failed:'更新失败，待补偿',obsolete:'旧版本'}
export const errorName: Record<string,string> = {LLM_TIMEOUT:'模型调用超时，可重试',LLM_NOT_CONFIGURED:'生成模型尚未配置',LLM_INVALID_RESPONSE:'模型服务未返回有效结构化结果',EXTRACTION_SCHEMA_INVALID:'模型输出结构不符合要求',OCR_NOT_INSTALLED:'OCR运行环境未安装',OCR_UNAVAILABLE:'本地OCR暂不可用',OCR_TIMEOUT:'OCR超时，可重试',AUTHORIZATION_REVOKED:'执行授权已撤销',FILE_HASH_MISMATCH:'原文件内容已变化',NO_READABLE_TEXT:'未读取到文字，请检查文件清晰度',DOCUMENT_SEGMENT_LIMIT:'文档超过500个文字片段限制',DOCUMENT_TEXT_LIMIT:'文字量超过12万字符读取限制',DOCUMENT_IMAGE_LIMIT:'文档图片超过100张限制',IMAGE_PIXEL_LIMIT:'图片超过2500万像素限制',RESUME_EXECUTION_FAILED:'解析执行失败，请检查文件或服务后重试',RECOVERY_EXHAUSTED:'中断恢复已达重试上限',EVIDENCE_MISMATCH:'无法核对原文依据',INVALID_PHONE:'电话格式异常',INVALID_EMAIL:'邮箱格式异常',INVALID_DATE_MONTH:'月份不在1至12之间',REVERSED_DATE_RANGE:'结束时间早于开始时间',AMBIGUOUS_IDENTITY:'存在多组身份信息，需人工核对'}

Object.assign(errorName,{PROFILE_EMPTY:"档案暂无可评估事实，请补充资料后新建匹配",EMBEDDING_UNAVAILABLE:"本地语义模型暂不可用，可重试",EMBEDDING_REBUILD_REQUIRED:"嵌入模型配置已变化，请用当前配置新建匹配",EMBEDDING_DIMENSION_MISMATCH:"嵌入维度不一致",EMBEDDING_INVALID_VECTOR:"嵌入结果无效，未生成语义分"})

errorName.RULE_VERSION_CHANGED="规则已更新，请发起新匹配；旧结果仅供历史核对"
