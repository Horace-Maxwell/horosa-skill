// Chapter bodies live in their own file (as the upstream 星运 manual keeps them in help/direction/chapters*.js).
import React from 'react';
import { p, ul, li, card, ct, kv, Lead, Section, Tip, Steps, OptionTable } from '../helpDocStyle';

const SHARED_LINE = '两章共用的一句话,来自模块级常量';

// A plain function component that is NOT marked __helpPure: the help dialog renders it, the reference walker skips it.
const SharedNote = ()=>(
	<p style={p}>共用片段:没有标记的函数组件,界面上照样显示。</p>
);

export const ALPHA_CHAPTERS = [
	{
		key: 'first',
		label: '第一法',
		aliases: ['one', 'First'],
		render: ()=>(
			<div>
				<Lead><b>第一法</b>是导语,讲清这一章做什么。</Lead>
				<Section title="原理与算法">
					<p style={p}>正文一段,带<b>加粗词</b>与 <i>斜体</i>。{SHARED_LINE}。</p>
					<div style={card}><div style={ct}>卡片标题</div>
						{kv('键一', '值一')}
						{kv('# 井号开头的键', <>值里有<b>加粗</b></>)}
					</div>
					<SharedNote />
				</Section>
				<Section title="设置逐项">
					<OptionTable rows={[
						{ name: '年长', values: '回归年 / 恒星年', def: '回归年' },
						{ name: '竖线', values: 'a | b', def: '无' },
					]} />
					<Steps items={['先选方法', '再看期表']} />
					<ul style={ul}>
						<li style={li}>列表一</li>
						<li style={li}>列表二:
							<ul style={ul}><li style={li}>子项甲</li><li style={li}>子项乙</li></ul>
						</li>
					</ul>
					<p style={p}># 井号开头的段落不是标题</p>
					<Tip tone="note">换盘会清掉查看位置。</Tip>
				</Section>
			</div>
		),
	},
	{
		key: 'second',
		label: '第二法',
		render: ()=>(
			<div>
				<Lead>第二法的导语。</Lead>
				<Section title="怎么读">
					<p style={p}>第二法正文,足够长的一段话,用来当作一章的内容。</p>
				</Section>
			</div>
		),
	},
];
