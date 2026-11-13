> 此方案已取消，仅保留历史接口。不得用于精确图片时钟成品，不得创建控制文件或恢复workflow；见[取消说明](../核验/AAC编码策略更新/旧5缓存迁移已取消.md)。以下内容为取消前的历史设计。

此迁移只用于原5篇已成功编码精听：2009-A、2009-B1、2009-B2、2024-A、2024-B1。2015-A、其他单元及任何显式AAC配置一律拒绝，不能拿迁移代替256k预检/新成片核验。

基线为c87cf30777f324ceabde3a0eba6a1a7ecfd54451。新两核心只增加可选audio.aac_bitrate三值验证、显式才写tm，以及两处tm.get默认192k。完整模块AST在去除该可选分支、把默认get还原192k后与c87相同。默认44单位的p、tm、原样PCM、可视路径及参数不变，核心依赖指纹变化须根显式刷新；不把fingerprint不同当PNG变化。

控制文件由根审核后创建、提交：`.github/tem8-listening-intensive-aac-cache-migration.json`。当前工具没有创建控制、没有自动approval。字段如下（占位内容不可提交）：

```json
{
  "schema": 1,
  "status": "approved",
  "branch": "codex/tem8-listening-2009-2024",
  "repository": "AlienCodes/university-entrance-examination",
  "target_release": "tem8-listening-render-cache-2009-2024",
  "proof_file": "专八/听力/批量/核验/AAC编码策略更新/默认44路径与真实参数正反例证明.json",
  "proof_sha256": "根最终复验后实际证明文件SHA256，不硬编码旧hash",
  "registry_sha256": "当前已批准审核登记.json的SHA256",
  "old_registry_sha256": "核验/AAC编码策略更新/旧审核登记.json的SHA256",
  "ids": ["2009-A", "2009-B1", "2009-B2", "2024-A", "2024-B1"],
  "old_fingerprints": {"逐ID": "根保存旧登记中的payload_sha256"},
  "old_mp4_sha256": {"逐ID": "真实旧资产SHA或Release服务器digest的SHA部分"},
  "evidence": "根对代码、原成品、真实等价证明及新registry的实际批准说明。"
}
```

`ids`可取旧5子集以续接，映射必须逐ID完整。新workflow为`migrate-tem8-intensive-aac-cache.yml`，只在已审分支push该控制时运行，单job串行迁移。只安装固定jieba以纯生成完整HTML，不启动浏览器、不运行音轨/视频编码。`run`要求相关代码/输入/控制/根证明/新旧registry均已提交，当前pub.gate有效且新旧实际PNG多重集相等。

只读检查单篇旧cache：

```sh
python3 专八/听力/批量/tools/迁移精听默认AAC缓存.py plan --id 2009-A --proof-sha256 根最终证明SHA --out /tmp/aac-plan
```

需要jieba==0.42.1；已有完整stage可传`--source`以免重复下载。plan不迁移、不上传，若新registry还未批准，只记录旧图，正式run仍强制新gate与全PNG摘要。

每篇先校原MP4/evidence的服务端SHA与ZIP CRC，再保留原pub.validate_stage全部约束。输入必须仍与c87逐字节相同、源语义不变、唯一依赖变化严格是已冻结两核心；读取真实p/tm、原声预演、截图/审批/成品完整报告，旧报告须成功且来源自洽。新旧实际states及完整逐屏HTML由真实缓存字锚/停顿数据重算并逐项相等，不能造时间；编码命令从真实函数AST及缓存真实帧数/路径提取作对照，不执行编码、不虚称新成片核验。未配置AAC的tm不得新增字段，必须仍是192k。

迁移只更新审批入口和新meta：旧meta/旧registry原字节、根冻结证明、逐帧/HTML/参数/图像等价记录加入`evidence/AAC默认兼容迁移/`。原source_commit/run_id、原verify/screens等报告及其旧fingerprint全部保留，另写current_registry/new approval fp/revalidated_commit/approval_migration。原MP4字节/大小/SHA不变；pub.store_stage按新fp持久保存后再次核服务端SHA。主render workflow及pub.gate不修改。

已做17个拒绝/逻辑测试，以及真实2009-A成功cache的完整只读检查；另在隔离副本上注入失败verify、改PNG并同步伪造库存摘要、改tm为256，三项均被拦，原cache未动。证据位于`核验/AAC编码策略更新/`。这些检查不是新视频编码或新成品verify。
