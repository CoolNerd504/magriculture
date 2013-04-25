// Tests for magri-ussd.js

var assert = require("assert");
var vumigo = require("vumigo_v01");
var app = require("../lib/magri-ussd");
var test_utils = vumigo.test_utils;


describe("test menu worker", function() {
    var tester = new test_utils.ImTester(app.api, {
        max_response_length: 160
    });

    it("new users should see the select_service state", function () {
        tester.check_state({
            user: null,
            content: null,
            next_state: "select_service",
            response: "^Hi Farmer Bob."
        });
    });
    it("select_service state should respond", function() {
        tester.check_state({
            user: {current_state: "select_service"},
            content: null,
            next_state: "select_service",
            response: ("^Hi Farmer Bob.[^]" +
                       "Select a service:[^]" +
                       "1. Market prices$")
        });
    });
    it("select_crop should respond", function() {
        tester.check_state({
            user: {current_state: "select_crop"},
            content: null,
            next_state: "select_crop",
            response: ("^Select a crop:[^]" +
                       "1. Peas[^]" +
                       "2. Carrots$")
        });
    });
    it("select_market_list should respond", function() {
        tester.check_state({
            user: {
                current_state: "select_market_list",
                custom: {
                    chosen_crop_name: "Peas"
                }
            },
            content: null,
            next_state: "select_market_list",
            response: ("^Select which markets to view:[^]" +
                       "1. All markets[^]" +
                       "2. Best markets for Peas$")
        });
    });
    it("select_market should respond (best_markets)", function() {
        tester.check_state({
            user: {
                current_state: "select_market",
                answers: {
                    select_crop: "crop1",
                    select_market_list: "best_markets"
                }
            },
            content: null,
            next_state: "select_market",
            response: ("^Select a market:[^]" +
                       "1. Kitwe[^]" +
                       "2. Ndola$")
        });
    });
    it("select_market should respond (all_markets)", function() {
        tester.check_state({
            user: {
                current_state: "select_market",
                answers: {
                    select_market_list: "all_markets"
                }
            },
            content: null,
            next_state: "select_market",
            response: ("^Select a market:[^]" +
                       "1. Kitwe[^]" +
                       "2. Ndola[^]" +
                       "3. Masala$")
        });
    });
    it("select_market should show_prices for selected market", function() {
        tester.check_state({
            user: {
                current_state: "select_market",
                answers: {
                    select_crop: "crop1"
                },
                custom: {
                    chosen_markets: [
                        ["market1", "Kitwe"],
                        ["market2", "Ndola"]
                    ],
                    chosen_crop_name: "Peas"
                },
            },
            content: "1",
            next_state: "show_prices",
            response: ("^Prices of Peas in Kitwe:[^]" +
                       "  boxes: 1.27[^]" +
                       "  crates: 1.70[^]" +
                       "Enter 1 for next market, 2 for previous market\.[^]" +
                       "Enter 3 to exit\.$")
        });
    });
    it("show_prices should move to previous market on 1", function() {
        tester.check_state({
            user: {
                current_state: "show_prices",
                answers: {
                    select_crop: "crop1"
                },
                pages: {
                    show_prices: 0
                },
                custom: {
                    chosen_markets: [
                        ["market1", "Kitwe"],
                        ["market2", "Ndola"]
                    ],
                    chosen_market_idx: 0,
                    chosen_crop_name: "Peas"
                }
            },
            content: "1",
            next_state: "show_prices",
            response: ("^Prices of Peas in Ndola:[^]" +
                       "  boxes: -[^]" +
                       "Enter 1 for next market, 2 for previous market\.[^]" +
                       "Enter 3 to exit\.$")
        });
    });
    it("show_prices should move to next market on 2", function() {
        tester.check_state({
            user: {
                current_state: "show_prices",
                answers: {
                    select_crop: "crop1"
                },
                pages: {
                    show_prices: 1
                },
                custom: {
                    chosen_markets: [
                        ["market1", "Kitwe"],
                        ["market2", "Ndola"]
                    ],
                    chosen_market_idx: 0,
                    chosen_crop_name: "Peas"
                }
            },
            content: "2",
            next_state: "show_prices",
            response: ("^Prices of Peas in Kitwe:[^]" +
                       "  boxes: 1.27[^]" +
                       "  crates: 1.70[^]" +
                       "Enter 1 for next market, 2 for previous market\.[^]" +
                       "Enter 3 to exit\.$")
        });
    });
    it("show_prices should move to end on 3", function() {
        tester.check_state({
            user: {
                current_state: "show_prices",
                custom: {
                    chosen_markets: [
                        ["market1", "Kitwe"],
                        ["market2", "Ndola"]
                    ],
                    chosen_market_idx: 0,
                    chosen_crop_name: "Peas"
               }
            },
            content: "3",
            next_state: "end",
            continue_session: false,
            response: ("^Goodbye!")
        });
    });
    it.skip("should sms prices selected", function () {
    });
});