"use client";

const AddSummonerForm = ({ handleSubmit, summonerName, setSummonerName, tagLine, setTagLine, formMessage, handleCancel }) => {
  return (
    <form className="add-summoner-form" onSubmit={handleSubmit}>
      <p className="form-hint">
        추가할 유저의 닉네임과 태그라인을 입력해주세요.<br />
        (태그라인 생략시 태그라인은 KR1으로 검색됩니다.)
      </p>
      <div className="form-row">
        <div className="form-group">
          <label htmlFor="summonerName" className="form-label">소환사명</label>
          <input
            id="summonerName"
            type="text"
            value={summonerName}
            onChange={(e) => setSummonerName(e.target.value)}
            required
            className="summoner-input"
            placeholder="예) Hide on bush"
          />
        </div>
        <div className="form-group">
          <label htmlFor="tagLine" className="form-label">태그라인</label>
          <input
            id="tagLine"
            type="text"
            value={tagLine}
            onChange={(e) => setTagLine(e.target.value)}
            className="summoner-input"
            placeholder="예) KR1"
          />
        </div>
      </div>
      
      {formMessage.text && (
        <div className={`form-message ${formMessage.type}`}>
          {formMessage.text}
        </div>
      )}

      <div className="form-buttons">
        <button type="submit" className="submit-btn">추가</button>
        <button type="button" className="cancel-btn" onClick={handleCancel}>취소</button>
      </div>
    </form>
  );
};

export default AddSummonerForm;
