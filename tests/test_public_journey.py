import asyncio
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_public_journey import Journey, JUNHONG, TDX, center, daily, inline_notice, nodes, tdx_search


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
        self.assertEqual(actions, ["open_market_once"])

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

    async def test_transient_incomplete_read_retries_without_input(self):
        class Missing(Exception):
            native_diagnostic = {"phase": "snapshot_incomplete_hierarchy"}
        calls, pauses = [], []
        async def capture(phase, options):
            calls.append(phase)
            if len(calls) == 1:
                raise Missing()
            return frame(chart())
        async def action(*args):
            self.fail("Read readiness must not inject input")
        async def pause(seconds):
            pauses.append(seconds)
        result, _ = await Journey(TDX, capture, action, pause).wait("ready", daily)
        self.assertEqual(result["foreground_package"], TDX)
        self.assertEqual(len(calls), 2)
        self.assertEqual(pauses, [2])

    async def test_missing_root_retries_remain_bounded_and_denied_roots_do_not_retry(self):
        for phase, expected_reads in (("snapshot_incomplete_hierarchy", 8),
                                      ("snapshot_foreground", 1), ("snapshot_sensitive", 1)):
            class Failure(Exception):
                native_diagnostic = {"phase": phase}
            calls = []
            async def capture(*args):
                calls.append(1)
                raise Failure()
            async def action(*args):
                self.fail("Unexpected action")
            async def pause(seconds):
                pass
            with self.subTest(phase=phase), self.assertRaises(Failure):
                await Journey(TDX, capture, action, pause).wait("ready", daily)
            self.assertEqual(len(calls), expected_reads)

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
