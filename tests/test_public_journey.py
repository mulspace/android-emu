import asyncio
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_public_journey import Journey, JUNHONG, TDX, center, daily, inline_notice, nodes, tdx_search, broker_result, broker_quote_ready, broker_layout_cancel


def node(**kw):
    return {"package": TDX, "class": "android.widget.TextView", "enabled": "true",
            "clickable": "true", "bounds": "[10,20][30,40]", **kw}


def frame(items, package=TDX):
    root = ET.Element("hierarchy")
    for item in items:
        ET.SubElement(root, "node", item)
    return {"foreground_package": package, "width": 720, "height": 1560, "rotation": 0,
            "hierarchy_xml": ET.tostring(root, encoding="unicode"), "frame_ref": "observed-frame",
            "sensitive_inputs": []}


def chart():
    return [node(text=t) for t in ("分时", "日K", "周K", "月K")]


def sequence(notice=False):
    market = frame([node(text="市场", selected="true", **{"resource-id": TDX + ":id/tvContent"}),
                    node(**{"class": "android.widget.ImageView", "bounds": "[648,71][693,116]"})])
    field = node(**{"class": "android.widget.EditText", "focused": "true",
                    "bounds": "[120,68][586,128]", "text": "股票代码/首字母/名称"})
    search = frame([field, node(text="搜索")])
    typed = deepcopy(search)
    typed["hierarchy_xml"] = typed["hierarchy_xml"].replace("股票代码/首字母/名称", "600999")
    result = frame([node(**{"content-desc": "招商证券\n15.68\n600999\n-1.13%"})])
    ready = frame(chart())
    daily_frame = frame(chart() + ([node(text="公开行情公告", bounds="[49,387][671,446]"),
        node(**{"class": "android.widget.LinearLayout", "bounds": "[671,387][701,446]"})] if notice else []))
    return [market, search, typed, result, deepcopy(result), ready, daily_frame] + ([ready] if notice else [])


class Selectors(unittest.TestCase):
    def test_fixed_search_requires_exact_context_not_just_coordinates(self):
        source = sequence()[0]
        self.assertIsNotNone(tdx_search(nodes(source, TDX)))
        source["hierarchy_xml"] = source["hierarchy_xml"].replace('selected="true"', 'selected="false"')
        self.assertIsNone(tdx_search(nodes(source, TDX)))

    def test_foreign_sensitive_or_changed_geometry_is_rejected(self):
        for delta in ({"foreground_package": JUNHONG}, {"sensitive_inputs": [{}]},
                      {"width": 1080}, {"rotation": 1}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                nodes({**frame(chart()), **delta}, TDX)

    def test_duplicate_and_unknown_close_controls_fail(self):
        with self.assertRaises(ValueError):
            daily(chart() + [node(text="日K")])
        with self.assertRaises(ValueError):
            inline_notice(chart() + [node(text="其它内容", bounds="[49,387][671,446]")])
        self.assertIsNone(inline_notice(chart() + [node(text="关闭")]))

    def test_broker_result_requires_exact_symbol_name_and_observed_row(self):
        items=[node(package=JUNHONG,text=value,bounds="[100,348][230,388]" if key != "et_input_edit" else "[178,73][538,113]",**{"resource-id":JUNHONG+":id/"+key})
               for key,value in {"et_input_edit":"600999","tv_stock_code":"600999","tv_stock_name":"招商证券","tv_stock_market":"沪A"}.items()]
        row=node(package=JUNHONG,bounds="[0,318][720,432]",**{"class":"android.widget.LinearLayout"})
        self.assertEqual(broker_result(items+[row]),row)
        self.assertIsNone(broker_result(items))
        moved=deepcopy(items);moved[1]["bounds"]="[100,500][230,540]"
        self.assertIsNone(broker_result(moved+[row]))
        for i in range(len(items)):
            changed=deepcopy(items);changed[i]["text"]="other"
            self.assertIsNone(broker_result(changed+[row]))
        with self.assertRaises(ValueError):broker_result(items+[row,row])
        self.assertIsNone(broker_quote_ready(items))

    def test_only_known_quote_layout_can_be_cancelled(self):
        labels={"tv_right":"五档在右边","tv_below":"五档在下边","tv_five_level_remind":"您还可以到“我的-设置-行情设置”里进行切换"}
        items=[node(package=JUNHONG,text=v,**{"resource-id":JUNHONG+":id/"+k}) for k,v in labels.items()]
        items.append(node(package=JUNHONG,text="五档/分时位置自由选择"))
        cancel=node(package=JUNHONG,text="取消",bounds="[40,977][359,1067]",**{"resource-id":JUNHONG+":id/tv_cancel"})
        self.assertEqual(broker_layout_cancel(items+[cancel]),cancel)
        self.assertIsNone(broker_layout_cancel([cancel]))
        for i in range(len(items)):
            self.assertIsNone(broker_layout_cancel(items[:i]+items[i+1:]+[cancel]))
        with self.assertRaises(ValueError):broker_layout_cancel(items+[cancel,cancel])

    def test_tap_requires_in_bounds_enabled_control(self):
        for delta in ({"bounds": "[-1,2][3,4]"}, {"bounds": "[0,0][721,1560]"},
                      {"clickable": "false"}, {"enabled": "false"}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                center(frame([]), node(**delta))


class Navigation(unittest.IsolatedAsyncioTestCase):
    async def test_broker_only_opens_public_market_and_never_trade_tab(self):
        pending = [frame([node(package=JUNHONG, text="行情", clickable="false",
                    **{"resource-id": JUNHONG + ":id/btm_text2"}),
                    node(package=JUNHONG, **{"resource-id": JUNHONG + ":id/bottom_menu_button2"})], JUNHONG)]
        tab = node(package=JUNHONG, text="行情", selected="false",
                   **{"resource-id": JUNHONG + ":id/tv_free_stock_market"})
        pending.append(frame([tab], JUNHONG))
        market = frame([{**tab, "selected": "true"}], JUNHONG)
        actions = []
        async def capture(phase, options):
            value = deepcopy(pending.pop(0) if pending else market)
            if "expected_frame_ref" in options:
                value["based_on_frame_ref"] = options["expected_frame_ref"]
            return value
        async def action(phase, operation, options):
            actions.append((phase, operation))
        await Journey(JUNHONG, capture, action).navigate()
        self.assertEqual(actions, [("open_market_once", "android.tap"),
                                   ("open_public_market_once", "android.tap")])

    async def test_broker_does_not_retap_selected_public_market(self):
        public = frame([node(package=JUNHONG, text="行情", clickable="false",
                    **{"resource-id": JUNHONG + ":id/btm_text2"}),
                    node(package=JUNHONG, **{"resource-id": JUNHONG + ":id/bottom_menu_button2"}),
                    node(package=JUNHONG, text="行情", selected="true",
                         **{"resource-id": JUNHONG + ":id/tv_free_stock_market"})], JUNHONG)
        actions = []
        async def capture(phase, options):
            result = deepcopy(public)
            if "expected_frame_ref" in options:
                result["based_on_frame_ref"] = options["expected_frame_ref"]
            return result
        async def action(phase, operation, options):
            actions.append(phase)
        await Journey(JUNHONG, capture, action).navigate()
        self.assertEqual(actions, [])

    async def test_optional_broker_search_only_types_public_symbol_once(self):
        home=frame([node(package=JUNHONG,text="行情",clickable="false",**{"resource-id":JUNHONG+":id/btm_text2"}),
                    node(package=JUNHONG,**{"resource-id":JUNHONG+":id/bottom_menu_button2"})],JUNHONG)
        market=frame([node(package=JUNHONG,text="行情",selected="true",**{"resource-id":JUNHONG+":id/tv_free_stock_market"})],JUNHONG)
        search=frame([node(package=JUNHONG,**{"resource-id":JUNHONG+":id/title_search","class":"android.widget.RelativeLayout","bounds":"[640,56][688,128]"})],JUNHONG)
        field=node(package=JUNHONG,text="",focused="true",password="false",**{"class":"android.widget.EditText"})
        typed=frame([{**field,"text":"600999"}],JUNHONG)
        pending=[home,market,search,frame([field],JUNHONG),typed,typed]
        actions=[]
        async def capture(phase,options):
            value=deepcopy(pending.pop(0) if pending else typed)
            if "expected_frame_ref" in options:value["based_on_frame_ref"]=options["expected_frame_ref"]
            return value
        async def action(phase,op,options):actions.append((phase,op,options))
        async def pause(seconds):pass
        await Journey(JUNHONG,capture,action,pause,junhong_page="search").navigate()
        self.assertEqual([a[0] for a in actions],["open_market_once","open_broker_public_search_once","enter_broker_public_symbol_once"])
        self.assertEqual(actions[-1][2]["text"],"600999")
        with self.assertRaises(ValueError):Journey(TDX,capture,action,junhong_page="search")

    async def test_broker_search_reuses_fresh_selected_market_frame(self):
        field=node(package=JUNHONG,text="",focused="true",password="false",**{"class":"android.widget.EditText"})
        market=frame([node(package=JUNHONG,text="行情",clickable="false",**{"resource-id":JUNHONG+":id/btm_text2"}),
            node(package=JUNHONG,**{"resource-id":JUNHONG+":id/bottom_menu_button2"}),
            node(package=JUNHONG,text="行情",selected="true",**{"resource-id":JUNHONG+":id/tv_free_stock_market"}),
            node(package=JUNHONG,**{"resource-id":JUNHONG+":id/title_search","class":"android.widget.RelativeLayout","bounds":"[640,56][688,128]"})],JUNHONG)
        market["frame_ref"]="original-market"
        typed=frame([{**field,"text":"600999"}],JUNHONG)
        pending=[market,frame([field],JUNHONG),typed,typed];reads=[];actions=[]
        async def capture(phase,options):
            reads.append(phase);value=deepcopy(pending.pop(0) if pending else typed)
            if "expected_frame_ref" in options:value["based_on_frame_ref"]=options["expected_frame_ref"]
            return value
        async def action(phase,op,options):actions.append((phase,op,options))
        async def pause(seconds):pass
        await Journey(JUNHONG,capture,action,pause,junhong_page="search").navigate()
        self.assertEqual([a[0] for a in actions],["open_broker_public_search_once","enter_broker_public_symbol_once"])
        self.assertEqual(actions[0][2]["frame_ref"],"original-market")
        self.assertFalse(any(r.startswith(("broker_search_control","market_ready","public_market_tab")) for r in reads))

    async def test_broker_quote_route_only_opens_verified_stock_row(self):
        search=frame([node(package=JUNHONG,text=value,bounds="[100,348][230,388]" if key != "et_input_edit" else "[178,73][538,113]",**{"resource-id":JUNHONG+":id/"+key})
               for key,value in {"et_input_edit":"600999","tv_stock_code":"600999","tv_stock_name":"招商证券","tv_stock_market":"沪A"}.items()]
               +[node(package=JUNHONG,bounds="[0,318][720,432]",**{"class":"android.widget.LinearLayout"})],JUNHONG)
        quote=frame([node(package=JUNHONG,text=t) for t in ("600999","招商证券","分时")],JUNHONG)
        pending=[search,search,quote];actions=[]
        async def capture(phase,options):
            result=deepcopy(pending.pop(0) if pending else quote)
            if "expected_frame_ref" in options:result["based_on_frame_ref"]=options["expected_frame_ref"]
            return result
        async def action(phase,op,options):actions.append((phase,op))
        async def pause(seconds):pass
        await Journey(JUNHONG,capture,action,pause,junhong_page="result").navigate()
        self.assertEqual(actions,[("open_broker_quote_once","android.tap")])

    async def test_complete_broker_quote_route_keeps_single_session_and_one_shot_input(self):
        for fail_tap in (False, True):
            with self.subTest(fail_tap=fail_tap):
                home = frame([
                    node(package=JUNHONG,text="行情",clickable="false",**{"resource-id":JUNHONG+":id/btm_text2"}),
                    node(package=JUNHONG,**{"resource-id":JUNHONG+":id/bottom_menu_button2"}),
                    node(package=JUNHONG,text="行情",selected="true",**{"resource-id":JUNHONG+":id/tv_free_stock_market"}),
                    node(package=JUNHONG,**{"resource-id":JUNHONG+":id/title_search","class":"android.widget.RelativeLayout","bounds":"[640,56][688,128]"})],JUNHONG)
                field=node(package=JUNHONG,text="",focused="true",password="false",**{"class":"android.widget.EditText"})
                typed=frame([{**field,"text":"600999"}],JUNHONG)
                result=frame([node(package=JUNHONG,text=value,bounds="[100,348][230,388]" if key != "et_input_edit" else "[178,73][538,113]",**{"resource-id":JUNHONG+":id/"+key})
                    for key,value in {"et_input_edit":"600999","tv_stock_code":"600999","tv_stock_name":"招商证券","tv_stock_market":"沪A"}.items()]
                    +[node(package=JUNHONG,bounds="[0,318][720,432]",**{"class":"android.widget.LinearLayout"})],JUNHONG)
                quote=frame([node(package=JUNHONG,text=t) for t in ("600999","招商证券","分时")],JUNHONG)
                pending=[home,frame([field],JUNHONG),typed,typed,result,result,quote]
                reads=[];actions=[]
                async def capture(phase,options):
                    reads.append(phase);value=deepcopy(pending.pop(0) if pending else quote)
                    if "expected_frame_ref" in options:value["based_on_frame_ref"]=options["expected_frame_ref"]
                    return value
                async def action(phase,op,options):
                    actions.append(phase)
                    if fail_tap and phase == "open_broker_quote_once":raise TimeoutError("uncertain input")
                async def pause(seconds):pass
                journey=Journey(JUNHONG,capture,action,pause,junhong_page="search-quote")
                if fail_tap:
                    with self.assertRaises(TimeoutError):await journey.navigate()
                    self.assertNotIn("broker_quote_entry_1",reads)
                    self.assertFalse(any(r.endswith("_checked") for r in reads))
                else:
                    await journey.navigate()
                    self.assertEqual(sum(r.endswith("_checked") for r in reads),3)
                self.assertEqual(actions,["open_broker_public_search_once","enter_broker_public_symbol_once","open_broker_quote_once"])

    async def test_known_layout_dialog_takes_priority_over_underlying_quote(self):
        quote=frame([node(package=JUNHONG,text=t) for t in ("600999","招商证券","分时")],JUNHONG)
        labels={"tv_right":"五档在右边","tv_below":"五档在下边","tv_five_level_remind":"您还可以到“我的-设置-行情设置”里进行切换"}
        modal=frame([node(package=JUNHONG,text=t) for t in ("600999","招商证券","分时","五档/分时位置自由选择")]
            +[node(package=JUNHONG,text=v,**{"resource-id":JUNHONG+":id/"+k}) for k,v in labels.items()]
            +[node(package=JUNHONG,text="取消",bounds="[40,977][359,1067]",**{"resource-id":JUNHONG+":id/tv_cancel"})],JUNHONG)
        pending=[modal,quote];actions=[]
        async def capture(phase,options):
            value=deepcopy(pending.pop(0) if pending else quote)
            if "expected_frame_ref" in options:value["based_on_frame_ref"]=options["expected_frame_ref"]
            return value
        async def action(phase,op,options):actions.append(phase)
        await Journey(JUNHONG,capture,action,junhong_page="quote").navigate()
        self.assertEqual(actions,["cancel_known_quote_layout_once"])

    async def test_tdx_existing_quote_never_replays_search_or_result_tap(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                actions=[];reads=[]
                async def capture(phase,options):
                    reads.append(phase)
                    if failed:raise TimeoutError("read failed")
                    value=frame(chart())
                    if "expected_frame_ref" in options:value["based_on_frame_ref"]=options["expected_frame_ref"]
                    return value
                async def action(phase,op,options):actions.append(phase)
                journey=Journey(TDX,capture,action,tdx_page="quote")
                if failed:
                    with self.assertRaises(TimeoutError):await journey.navigate()
                    self.assertEqual(actions,[]);self.assertEqual(reads,["chart_ready_1"])
                else:
                    await journey.navigate()
                    self.assertEqual(actions,["select_daily_once"])
                    self.assertEqual(sum(r.endswith("_checked") for r in reads),3)
                with self.assertRaises(ValueError):Journey(JUNHONG,capture,action,tdx_page="quote")
                with self.assertRaises(ValueError):Journey(TDX,capture,action,tdx_page="unknown")

    async def scenario(self, *, notice=False, failed_action=None, changed_pair=False):
        pending, actions, reads = sequence(notice), [], []
        last = frame(chart())
        async def capture(phase, options):
            reads.append(phase)
            current = deepcopy(pending.pop(0) if pending else last)
            if "expected_frame_ref" in options:
                current["based_on_frame_ref"] = options["expected_frame_ref"]
                if changed_pair:
                    current["hierarchy_xml"] += " "
            return current
        async def action(phase, operation, options):
            actions.append((phase, operation, options))
            if phase == failed_action:
                raise TimeoutError("Uncertain action")
        try:
            async def pause(seconds):
                pass
            await Journey(TDX, capture, action, pause).navigate()
        except (TimeoutError, ValueError):
            if failed_action is None and not changed_pair:
                raise
        return actions, reads

    async def test_full_public_journey_one_action_each_and_three_bound_pairs(self):
        actions, reads = await self.scenario(notice=True)
        self.assertEqual(len(actions), 6)
        self.assertEqual(len(set(a[0] for a in actions)), 6)
        self.assertEqual([a[2]["text"] for a in actions if a[1] == "android.text"], ["600999"])
        self.assertEqual(len([r for r in reads if r.endswith("_checked")]), 3)

    async def test_uncertain_input_never_replays_or_advances(self):
        actions, reads = await self.scenario(failed_action="enter_public_symbol_once")
        self.assertEqual([a[0] for a in actions], ["open_search_once", "enter_public_symbol_once"])
        self.assertNotIn("symbol_readback_1", reads)

    async def test_changed_expected_image_fails_without_advancing_frame(self):
        _, reads = await self.scenario(changed_pair=True)
        self.assertIn("snapshot_1_checked", reads)
        self.assertNotIn("snapshot_2_observe", reads)

    async def test_loading_reads_bounded_and_never_click_unknown_dialog(self):
        calls, pauses = [], []
        async def capture(phase, options):
            calls.append(phase)
            return frame([node(text="是否更新？")])
        async def action(*args):
            self.fail("Unexpected action")
        async def pause(delay):
            pauses.append(delay)
        with self.assertRaises(TimeoutError):
            await Journey(TDX, capture, action, pause).navigate()
        self.assertEqual(len(calls), 8)
        self.assertEqual(pauses, [2] * 7)

    async def test_stable_control_requires_consecutive_matches_and_returns_latest_frame(self):
        pending = [frame([node(text="日K", bounds=b)] + [node(text="分时"), node(text="周K"), node(text="月K")])
                   for b in ("[0,0][10,10]", "[10,10][20,20]", "[10,10][20,20]")]
        for i, value in enumerate(pending): value["frame_ref"] = str(i)
        calls = []
        async def capture(phase, options):
            calls.append(phase); return pending.pop(0)
        async def action(*args): self.fail("Readiness must not click")
        async def pause(seconds): pass
        result, chosen = await Journey(TDX,capture,action,pause).wait("stable",daily,stable=True)
        self.assertEqual(result["frame_ref"], "2")
        self.assertEqual(chosen["bounds"], "[10,10][20,20]")
        self.assertEqual(len(calls),3)

    async def test_native_failure_ends_session_and_never_retries_rpc(self):
        for phase in ("snapshot_incomplete_hierarchy", "snapshot_foreground", "snapshot_sensitive"):
            class Failure(Exception):
                native_diagnostic = {"phase": phase}
            calls = []
            async def capture(*args):
                calls.append(1)
                raise Failure()
            async def action(*args): self.fail("Unexpected action")
            async def pause(seconds): self.fail("A failed native session cannot be reused")
            with self.subTest(phase=phase), self.assertRaises(Failure):
                await Journey(TDX, capture, action, pause).wait("ready", daily)
            self.assertEqual(len(calls), 1)

    async def test_failed_snapshot_stops_immediately(self):
        calls = []
        async def capture(phase, options):
            calls.append(phase)
            raise TimeoutError("Native timeout")
        async def action(*args):
            self.fail("Unexpected action")
        with self.assertRaises(TimeoutError):
            await Journey(TDX, capture, action).navigate()
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
