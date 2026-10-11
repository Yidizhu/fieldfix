/* Presentation only. Payment permissions remain enforced by the server. */
(function (root) {
  "use strict";
  function focus(state) {
    const payment=state.payment, pending=state.pending_operation;
    const pendingAction=typeof pending==="string"?pending:(pending?.action||pending?.operation||pending?.type||"");
    const legacy=!!(state.legacy||state.legacy_payment||(payment&&payment.intent!=="AUTHORIZE"));
    if(legacy)return {stages:[3],reason:"legacy"};
    if(pending)return {stages:[3,...(["capture","void"].includes(pendingAction)?[5]:[])],reason:"pending"};
    if(payment&&!["authorized","completed","voided"].includes(payment.status))return {stages:[3],reason:"payment"};
    if(payment&&["completed","voided"].includes(payment.status))return {stages:[5],reason:payment.status};
    if(!state.review)return {stages:[1],reason:"review"};
    if(state.review.decision==="warranty")return {stages:[2],reason:"warranty"};
    if(state.review.decision==="replace"){
      if(!state.approved)return {stages:[2],reason:"quote"};
      if(!payment)return {stages:[3],reason:"authorize"};
      if(state.repair==="verified_demo"&&state.recovery?.status==="pass")return {stages:[5],reason:"charge"};
      // Retain the no-charge exit while evidence is being checked.
      return {stages:[4],reason:"recovery"};
    }
    return {stages:[4],reason:state.repair==="verified_demo"?"reviewed":"recovery"};
  }
  function progress(state, {needsReview=false, normal=false}={}) {
    const effective=needsReview&&!state.payment?{...state,review:null,approved:false}:state;
    const reason=focus(effective).reason;
    if(reason==="review"&&normal&&!needsReview)return "normal";
    if(reason==="payment")return state.payment?.status==="awaiting_buyer"?"authorize":"payment_check";
    return reason;
  }
  const api=Object.freeze({focus,progress});
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  else root.FieldFixFlowView=api;
})(typeof window!=="undefined"?window:globalThis);
