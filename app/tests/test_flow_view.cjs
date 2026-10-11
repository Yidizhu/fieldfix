const assert=require('node:assert/strict');
const {focus}=require('../static/flow-view.js');
const base={review:null,approved:false,payment:null,repair:'unverified',recovery:null};
const replace={...base,review:{decision:'replace'}};
const approved={...replace,approved:true};
const authorized={...approved,payment:{intent:'AUTHORIZE',status:'authorized'}};
const checks=[
  [base,[1]], [replace,[2]], [approved,[3]],
  [{...base,review:{decision:'warranty'}},[2]],
  [{...base,review:{decision:'observe'}},[4]],
  [authorized,[4]],
  [{...authorized,recovery:{status:'pass'}},[4]],
  [{...authorized,recovery:{status:'fail'},repair:'verified_demo'},[4]],
  [{...authorized,recovery:{status:'insufficient'},repair:'verified_demo'},[4]],
  [{...authorized,recovery:{status:'pass'},repair:'verified_demo'},[5]],
  [{...base,pending_operation:{action:'create_order'}},[3]],
  [{...authorized,pending_operation:{action:'capture'}},[3,5]],
  [{...authorized,pending_operation:{action:'void'}},[3,5]],
  [{...authorized,payment:{intent:'CAPTURE',status:'completed'}},[3]],
  ...['awaiting_buyer','pending','expired','denied','unrecognized'].map(status=>[{...authorized,payment:{intent:'AUTHORIZE',status}},[3]]),
  ...['completed','voided'].map(status=>[{...authorized,payment:{intent:'AUTHORIZE',status}},[5]])
];
for(const [state,expected] of checks){const before=JSON.stringify(state);assert.deepEqual(focus(state).stages,expected);assert.equal(JSON.stringify(state),before);}
console.log(`${checks.length} workflow presentation checks passed; inputs unchanged.`);
